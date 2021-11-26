#Setup steps

As a result of these steps, you will be available to create and see information on a deployed block chain running 4 nodes on 4 different Google Cloud virtual machines.

Example url:
http://35.228.5.168:9000

### 0. Set up environment
  - root folder: ./init.sh

### 1. Update indy-node.dockerfile
  - modify nodeNum parameter
  - modify ips parameter

### 2. Initiate indy nodes
  - root folder: docker-compose up -d
  
### 3. Build admin ui
  - cd von-network
  - ./manage build

### 4. Run admin ui
  - update ip address in start_admin_ui.sh with genesis url
  - cd von-network
  - ./indy-node-start.sh

### 5. Add date to indy nodes
  - cd add_data
  - update ip address in indy-node-data.dockerfile with genesis url
  - docker-compose up -d

### 6. Add new steward
  - cd add_steward
  - update ip address in indy-node-data.dockerfile with genesis url
  - docker-compose up -d

  
 