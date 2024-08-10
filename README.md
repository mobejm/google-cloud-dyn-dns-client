# Google Cloud Dynamic DNS Client

This is a Python DynDNS client for [google-cloud-function-dyn-dns](https://github.com/mobejm/google-cloud-functions-dyn-dns). It is meant to be deployed on-prem or in a home-lab to detect changes in the Public IP address and update the corresponding DNS record using the Google Cloud function.

- Only IPv4 is supported at the moment (DNS A records)
- Only a single IPv4 is supported per DNS A record
- The script uses several free third-party APIs to obtain the current Public IP. This is more cost-effective (monetarily speaking) than calling the Google Cloud DynDNS function every time and have it detect changes in the Public IP (not even supported at the moment).
- The script will also perform DNS queries regularly (interval is configurable) to obtain the current IP address associated with the DNS A record being updated. This operation is quite inexpensive (see [Cloud DNS Pricing](https://cloud.google.com/dns/pricing)). 

---

***IMPORTANT***: This project only supports using a Google Cloud Service Account to obtain and renew the Token ID necessary to call the Google Cloud Function for DynDNS. For security reasons, it's generally advised against using Service Accounts for running tools or services outside of Google Cloud. Simply the act of downloading a Service Account `key` is considered a security risk. For this reason it's **VERY IMPORTANT** to create a Service Account specifically for this tool and with the minimum set of permissions necessary for it to work. This would drastically reduce the blast-radius of a security incident where the `key` gets compromised. Please keep this in mind when using this project, if this is just for a home-lab or testing it's probably okay but maybe not so for a business solution.

---

## 1. Pre-requisites

- Python 3
- A Google Cloud project must already exist with the [Google Cloud Dynamic DNS Function]((https://github.com/mobejm/google-cloud-functions-dyn-dns)) deployed and ready to accept requests.
- A Google Cloud Service Account with `invoke` permissions to the DynDNS cloud function. Follow these instructions to create one using the `gcloud` CLI (go [here](https://cloud.google.com/sdk/docs/install-sdk) for instructions on how to install the CLI):
    - Log in with an account that has permissions to create Service Accounts. Several roles include this permission like `Owner`, `roles/iam.serviceAccountAdmin`, `roles/iam.serviceAccountCreator`, etc.
        ```
        gcloud auth login 
        ```
    - Create the Service Account.
        ```
        gcloud iam service-accounts create {service-account-name} --description="{Service Account Description}" --display-name="{Service Account Display Name}"
        ```
    - Ensure the service account was created successfully:
        ```
        gcloud iam service-accounts list
        ```
    - Give the service account permissions to call the DynDNS Google Cloud Function
        - `{region-name}` is the name of the region where the function was deployed
        - `{service-account-name}` is the name of the serivce account that was create earlier
        - `{project-name}` Id of the project
        ```
        gcloud functions add-iam-policy-binding update_dns_a_record --region="{region-name}" --role="roles/cloudfunctions.invoker" --member="serviceAccount:{service-account-name}@{project-id}.iam.gserviceaccount.com"
        ```
    - If you haven't created a key for the service account, you can execute the following command to create one. Make sure to keep the key file safe.
        ```
        gcloud iam service-accounts keys create {key-file-name} --iam-account={service-account-name}@{project-id}.iam.gserviceaccount.com
        ```
    - The generated key file is what the `GOOGLE_APPLICATION_CREDENTIALS` environment variable should point to before running this tool.

## 2. Instructions

1. Create a virtual environment in a folder within the codebase
    ```
    python -m venv venv
    ```
1. Activate the virtual environment
    ```
    source ./venv/bin/activate
    ```
1. Install requirements
    ```
    pip install -r requirements.txt
    ```
1. Create an `.env` file with the following environment variables (please change them accordingly):
    ```
    ZONE_NAME=domain-com
    ZONE_DNS_NAME=domain.com.
    DYN_DNS_API_URL=https:/{region}-{project}.cloudfunctions.net/{function-name}
    HOSTNAME=test.domain.com.
    GOOGLE_APPLICATION_CREDENTIALS=/path/to/auth/file.json
    DNS_RECORD_DEFAULT_TTL=300
    PUBLIC_IP_CHECK_INTERVAL_SEC=300
    ```
1. Run the tests:
    ```
    python3 -m unittest tests/test_*
    ```
## 3. Configuration

| Variable                       | Description |
| ------------------------------ | ----------- |
| GOOGLE_APPLICATION_CREDENTIALS | Path to the key file for the service account to be used to call the DynDNS Google Cloud Function. |
| ZONE_NAME                      | Name of the Zone as shown in Google Cloud |
| ZONE_DNS_NAME                  | DNS Name of the Zone as shown in Google Cloud |
| DYN_DNS_API_URL                | URL for the DynDNS Google Cloud Function |
| HOSTNAME                       | DNS name of the record to be updated |
| DNS_RECORD_DEFAULT_TTL         | This defines how often the script will perform a DNS query to obtain the curren Public IP assigned to the DNS name |
| PUBLIC_IP_CHECK_INTERVAL_SEC   | Defines how often the script will call one of the free third-party APIs to obtain the Public IP |
| PID_FILE_PATH                  | If defined, a PID file will be created in the specified location |