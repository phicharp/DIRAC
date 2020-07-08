#!/usr/bin/env python

"""
  Get the transformations belonging to a given production
"""

__RCSID__ = "2bf8e43be (2018-11-21 10:55:53 +0100) arrabito <arrabito@in2p3.fr>"

import DIRAC
from DIRAC.Core.Base import Script
from DIRAC.Core.Utilities.PrettyPrint import printTable

Script.setUsageMessage('\n'.join([__doc__.split('\n')[1],
                                  'Usage:',
                                  '  %s prodID' % Script.scriptName,
                                  'Arguments:',
                                  '  prodID: Production ID',
                                  '\ne.g: %s 381' % Script.scriptName,
                                  ]))


Script.parseCommandLine()

from DIRAC.ProductionSystem.Client.ProductionClient import ProductionClient
from DIRAC.TransformationSystem.Client.TransformationClient import TransformationClient

args = Script.getPositionalArgs()
if (len(args) != 1):
  Script.showHelp()

# get arguments
prodID = args[0]

prodClient = ProductionClient()
transClient = TransformationClient()

res = prodClient.getProductionTransformations(prodID)
transIDs = []

if res['OK']:
  transList = res['Value']
  if len(transList) == 0:
    DIRAC.gLogger.notice('No transformation associated with production %s' % prodID)
    DIRAC.exit(-1)
  else:
    for trans in transList:
      transIDs.append(trans['TransformationID'])
else:
  DIRAC.gLogger.error(res['Message'])
  DIRAC.exit(-1)


fields = ['TransformationName', 'Status', 'F_Proc.', 'F_Proc.(%)', 'TransformationID', 'ProductionID', 'Prod_LastUpdate',
          'Prod_InsertedTime']

records = []

paramShowNames = ['TransformationID', 'TransformationName', 'Type', 'Status', 'Files_Total', 'Files_PercentProcessed',
                  'Files_Processed', 'Files_Unused', 'Jobs_TotalCreated', 'Jobs_Waiting',
                  'Jobs_Running', 'Jobs_Done', 'Jobs_Failed', 'Jobs_Stalled']
resList = []


res = transClient.getTransformationSummaryWeb({'TransformationID': transIDs}, [], 0, len(transIDs))

if not res['OK']:
  DIRAC.gLogger.error(res['Message'])
  DIRAC.exit(-1)
  
if res['Value']['TotalRecords'] > 0:
  paramNames = res['Value']['ParameterNames']
  for paramValues in res['Value']['Records']:
    paramShowValues = map(lambda pname: paramValues[paramNames.index(pname)], paramShowNames)
    showDict = dict(zip(paramShowNames, paramShowValues))
    resList.append(showDict)

for res in resList:
  files_Processed = res['Files_Processed']
  files_PercentProcessed = res['Files_PercentProcessed']
  status = res['Status']
  type = res['Type']
  transName = res['TransformationName']
  transID = res['TransformationID']
  records.append([transName, status, str(files_Processed), str(files_PercentProcessed), str(transID), str(prodID),
                  str(trans['LastUpdate']), str(trans['InsertedTime'])])


printTable(fields, records)

DIRAC.exit(0)
