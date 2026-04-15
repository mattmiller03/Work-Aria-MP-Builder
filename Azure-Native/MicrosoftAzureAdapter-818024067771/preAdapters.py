'''
@author: svantmuri
'''
#!/usr/bin/env python
# Copyright 2022 VMware, Inc.  All rights reserved. -- VMware Confidential

__author__ = "VMware, Inc."

import argparse
import os
import subprocess
import json
import shutil
import glob
import platform
import re
import sys
import time

startingDir = os.getcwd()
OPSCLI_DIRECTORY = os.path.join(os.environ['VCOPS_BASE'], 'tools', 'opscli')
OPSCLI_SHELL = "./ops-cli.sh "


def constructOPSCLICommand(argumentsString):
    scriptCommand = OPSCLI_SHELL
    scriptWithArgs = scriptCommand + argumentsString
    print('Constructed script command: "{0}"'.format(scriptWithArgs))
    return scriptWithArgs

def delete_dashboards(tabIds):
    # OPSCLI must be run from the OPSCLI directory.
    startingDir = os.getcwd()
    os.chdir(OPSCLI_DIRECTORY)
    print("Deleting Azure dashboards with IDs " + tabIds)
    args = ['admin {0}'.format(tabIds)]
    scriptCommand = constructOPSCLICommand('dashboard delete_ids {0}'.format(' '.join(args)))
    returnCode = subprocess.call(scriptCommand, shell=True)
    print("Command return code={0}".format(returnCode))
    # Return to the original directory.
    os.chdir(startingDir)

print("Pre install script for Azure Adapter")
parser = argparse.ArgumentParser(description="Post-upgrade script for the Azure MP Solution")
parser.add_argument('-f', '--force_content_update', choices=['True', 'true', 'False', 'false'],
   dest='forceContentUpdate', default='False', help="Force out-of-the-box content update")
parser.add_argument('--authToken',help='Authorization token to make REST API calls')
parser.add_argument('--roles', help='User roles')
(args, remainder) = parser.parse_known_args()

forceContentUpdate = args.forceContentUpdate.lower() == "true"
roles = args.roles
authToken = args.authToken
print("forceContentUpdate is set to '{0}', unparsed arguments are: {1}".format(forceContentUpdate, remainder))
print("Roles: {0}".format(roles))

print("Deleting Old Dashboards")
if 'ADMIN' in roles and 'REPLICA' not in roles:
    delete_dashboards("'98790a1e-49c0-4072-96b4-82d5d2de98b2,7f060add-3e19-4179-aed7-3a095165f325,3d418ebc-ffa7-4c7a-889e-c172d6df9876,be0844d1-1ec0-47e6-bfdd-a74d82093125,d72ad7f4-a3f9-4f36-9c4a-b9ff60fea347,514ab55d-4a65-4cf8-8b41-8b10e8e84a50,6922c496-04a0-4c30-8e0f-d48f02865d94,502d6d93-2c74-406d-b987-87908c5e26e9,6b0f657d-0d1e-4f36-87b1-892a6bbcd130,d52bd70d-6280-45f9-9a2e-a5bcbeab4019,cfd23c84-c0de-4d43-95f0-facc161fe7cf,34ab0796-44e0-4038-b1b4-355db82b08c4,7850429d-132a-4beb-81c0-bdc2a1be9d59,6485a199-ae61-4152-8e10-8c1048a589f6,9e1c8aad-e193-4243-b9ac-97dad5ec4f07,a00324c1-805c-41b5-b9b2-68b16c45eb8f'")
    time.sleep(60)
else:
    print('Non-primary node. Skipping Dashboard and Action Plugin configuration.')

print("Successfully completed pre install script for Azure Adapter.")