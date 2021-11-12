# iroha-deploy
This repo is used to deploy multiple replicas of Iroha containers (one Iroha peer per container) on remote or local hosts.


## Configure nodes
Depending on the number of nodes that you will deploy, create yaml files in the `playbooks/iroha-docker/host_vars` directory that describe your nodes. Check [Example 2] (https://github.com/hyperledger/iroha-deploy/blob/main/ansible/roles/iroha-docker/README.md).


## Run playbooks
Locally - Run:
```
ansible-playbook -e 'iroha_network=internal' -c local  -i 'localhost,' playbooks/iroha-docker/main.yml -b -K`
```

Remote Hosts - Run:
```
ansible-playbook -i inventory/iroha.list -b playbooks/iroha-docker/main.yml
```