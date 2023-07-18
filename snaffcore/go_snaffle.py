import sys
import socket
import urllib.parse
import dns.resolver

from ldap3 import ALL_ATTRIBUTES, Server, Connection, DSA, ALL, SUBTREE
from time import sleep
from .smb import *
from .utilities import *
from .file import *
from .classifier import *

log = logging.getLogger('snafflepy')


def begin_snaffle(options):
    print("Beginning the snaffle...")
    sleep(0.2)

    domain_names = []
    # TODO: Talk to AD via LDAP to get list of computers with file shares
    if options.disable_computer_discovery:
        log.info(
            "Computer discovery is turned off. Snaffling will only occur on the host(s) specified.")

    else:
        login = access_ldap_server(
            options.targets[0], options.username, options.password)
        domain_names = list_computers(login, options.domain)
        # list_computers() returns list so need to individually add entry
        for target in domain_names:
            log.debug(
                f"Found{target}, adding to targets to snaffle...")
            sleep(0.5)
            try:
                # TODO: Try to fix this? - How to resolve local IP address from Hostname
                # Supposedly SMBConnection should be able to take a hostname but not working as intended on the HTB enviroment I am using for testing
                # ip = resolve(options.domain, target)
                options.targets.append(target)
            except Exception as e:
                log.debug(f"Exception: {e}")
                log.warning(f"Unable to add{target} to targets to snaffle")
                continue
    log.info(f"Targets that will be snaffled: {options.targets}")

    # Login via SMB
    # log.info("Preparing classifiers...")
    # prepare_classifiers()

    if options.no_share_discovery:
        try:
            smb_client = SMBClient(
                options.targets[0], options.username, options.password, options.domain, options.hash)
        except:
            log.error(f"Error logging in to SMB on {options.targets[0]}")

    else:
        log.info("Enumerating shares for files...")
        for target in options.targets:
            try:
                smb_client = SMBClient(
                    target, options.username, options.password, options.domain, options.hash)
                smb_client.login()
                for share in smb_client.shares:
                    try:
                        files = smb_client.ls(share, "")
                        
                        for file in files:
                            # filelist.append(file)
                            # Ask do they want file sizes?
                            # log.info(f"{target} Found file in {share}: {file.get_longname()}")
                            naive_classify(share, file)
                            # log.info(f"{target} Found file in {share}: {file}")
                    except FileListError:
                        log.error(
                            "Access Denied, cannot list files in %s" % share)
                        continue

            except Exception as e:
                log.error(f"Error creating SMBClient object, {e}")


def access_ldap_server(ip, username, password):
    log.info("Accessing LDAP Server")
    server = Server(ip, get_info=DSA)
    try:
        conn = Connection(server, username, password)
        # log.debug(server.schema)

        if not conn.bind():
            log.critical(f"Unable to bind to {server} as {username}, ")
        return conn

    except Exception as e:
        log.critical(f'Error logging in to {ip}')
        log.info("Trying guest session... ")

        try:
            conn = Connection(server, username='Guest', password='')
            if not conn.bind():
                log.critical(f"Unable to bind to {server} as {username}")
            return conn

        except Exception as e:
            log.critical(f'Error logging in to {ip}, as {username}')
            log.info("Trying null session... ")

            conn = Connection(server, username='', password='')
            if not conn.bind():
                log.critical(f"Unable to bind to {server} as {username}")
                return None
            return conn

# 2nd snaffle step, finding additional targets from original target via LDAP queries


def list_computers(connection: Connection, domain):
    dn = get_domain_dn(domain)
    # filter = "(objectCategory=computer)"
    if connection is None:
        log.critical("Connection is not established")

    try:
        connection.search(search_base=dn, search_filter='(&(objectCategory=Computer)(name=*))',
                          search_scope=SUBTREE, attributes=['dNSHostName'], paged_size=500)
        # log.debug(connection.entries)
        # connection.search(search_base=dn,search_filter=filter,search_scope=SUBTREE,attributes=ALL_ATTRIBUTES)
        domain_names = []

        log.debug(connection.entries)
        for entry in connection.entries:
            sep = str(entry).strip().split(':')
            domain_names.append(sep[6])

        return domain_names

    except Exception as e:
        log.critical(f"Unable to list computers: {e}")
        return None

# TODO
def naive_classify(share, file):
    log.info(f"{share}: {file.get_longname()}")

    if is_interest(file):
        log.info(f"Found interesting file: {share}/{file}")


# def resolve(nameserver, host_fqdn):
#     resolver = dns.resolver.Resolver()
#     resolver.nameservers = [nameserver]
#     answer = resolver.query(host_fqdn, "A")
#     return answer


# def get_ip(target):
#     try:
#         print(socket.gethostbyname(target))
#     except socket.gaierror:
#         parsed_url = urllib.parse.urlparse(target)
#         hostname = parsed_url.hostname
#         try:
#             answers = dns.resolver.query(hostname, 'A')
#             for rdata in answers:
#                 print(rdata.address)
#         except dns.resolver.NXDOMAIN:
#             print('ip not found')
