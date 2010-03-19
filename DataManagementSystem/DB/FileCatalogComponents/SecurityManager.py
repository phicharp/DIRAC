########################################################################
# $HeadURL:  $
########################################################################
""" DIRAC FileCatalog Security Manager mix-in class
"""

__RCSID__ = "$Id:  $"

import time
from DIRAC import S_OK, S_ERROR, gConfig

class SecurityManagerBase:
  
  def __init__(self,database=False):
    self.db = database
    
  def setDatabase(self,database):
    self.db = database
    
  def hasAccess(self,opType,paths,credDict):
    successful = {}
    if not opType.lower() in ['read','write']:
      return S_ERROR("Operation type not known")
    for path in paths:
      successful[path] = False
    resDict = {'Successful':successful,'Failed':{}}
    return S_OK(resDict)

  def hasAdminAccess(self,credDict):
    if credDict.get('username','') == 'diracAdmin':
      return S_OK(True)
    return S_OK(False)

class NoSecurityManager(SecurityManagerBase):

  def hasAccess(self,opType,paths,credDict):
    successful = {}
    for path in paths:
      successful[path] = True
    resDict = {'Successful':successful,'Failed':{}}
    return S_OK(resDict)

  def hasAdminAccess(self,credDict):
    return S_OK(True)

class DirectorySecurityManager(SecurityManagerBase):
  pass

class FullSecurityManager(SecurityManagerBase):
  pass
