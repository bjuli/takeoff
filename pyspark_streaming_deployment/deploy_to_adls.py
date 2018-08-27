import glob

from azure.datalake.store import core, lib, multithread

from pyspark_streaming_deployment.util import get_application_name, read_azure_sp

ADLS_STORE_NAME = 'sdhdatalakestore{dtap}'


def upload_to_adls(client, source: str, destination: str):
    print(f"""uploading artifact from
     | from ${source}
     | to ${destination}""")

    multithread.ADLUploader(client,
                            lpath=source,
                            rpath=destination,
                            overwrite=True)


def deploy_application_to_adls(version: str, dtap: str):
    print("Submitting job to databricks")

    azure_sp = read_azure_sp(dtap)
    azure_adls_name = ADLS_STORE_NAME.format(dtap=dtap.lower())
    build_definitionname = get_application_name()

    adls_credentials = lib.auth(tenant_id=azure_sp.tenant,
                                client_secret=azure_sp.password,
                                client_id=azure_sp.username,
                                resource='https://datalake.azure.net/')
    adls_client = core.AzureDLFileSystem(adls_credentials, store_name=azure_adls_name)

    eggs = glob.glob('/root/dist/*.egg')
    if len(eggs) != 1:
        raise FileNotFoundError(f'Eggs found: {eggs}; There can (and must) be only one!')

    egg = eggs[0]
    main = '/root/main/main.py'

    upload_to_adls(adls_client,
                   egg,
                   f'/libraries/{build_definitionname}/{build_definitionname}-{version}.egg')
    upload_to_adls(adls_client,
                   main,
                   f'/libraries/{build_definitionname}/{build_definitionname}-main-{version}.py')
