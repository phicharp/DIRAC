# $Header: /tmp/libdirac/tmp.stZoy15380/dirac/DIRAC3/DIRAC/ConfigurationSystem/private/ConfigurationData.py,v 1.15 2008/06/02 18:04:13 acasajus Exp $
__RCSID__ = "$Id: ConfigurationData.py,v 1.15 2008/06/02 18:04:13 acasajus Exp $"

import os.path
import zlib
import zipfile
import threading
import time
import DIRAC
from DIRAC.Core.Utilities import List, Time
from DIRAC.Core.Utilities.ReturnValues import S_OK, S_ERROR
from DIRAC.ConfigurationSystem.Client.CFG import CFG
from DIRAC.LoggingSystem.Client.Logger import gLogger

class ConfigurationData:

  def __init__( self, loadDefaultCFG = True ):
    self.threadingEvent = threading.Event()
    self.threadingEvent.set()
    self.threadingLock = threading.Lock()
    self.runningThreadsNumber = 0
    self.compressedConfigurationData= ""
    self.configurationPath = "/DIRAC/Configuration"
    self.backupsDir = "%s/etc/csbackup" % DIRAC.rootPath
    self.isService = False
    self.localCFG = CFG()
    self.remoteCFG = CFG()
    if loadDefaultCFG:
      defaultCFGFile = "%s/etc/dirac.cfg" % DIRAC.rootPath
      gLogger.debug( "dirac.cfg should be at", "%s" % defaultCFGFile )
      retVal = self.loadFile( defaultCFGFile )
      if not retVal[ 'OK' ]:
        gLogger.error( "Can't load %s file" % defaultCFGFile )
    self.sync()

  def getBackupDir( self ):
    return self.backupsDir

  def sync( self ):
    gLogger.debug( "Updating configuration internals" )
    self.mergedCFG = self.remoteCFG.mergeWith( self.localCFG )
    self.remoteServerList = []
    localServers = self.extractOptionFromCFG( "%s/Servers" % self.configurationPath,
                                        self.localCFG )
    if localServers:
      self.remoteServerList.extend( List.fromChar( localServers, "," ) )
    remoteServers = self.extractOptionFromCFG( "%s/Servers" % self.configurationPath,
                                        self.remoteCFG )
    if remoteServers:
      self.remoteServerList.extend( List.fromChar( remoteServers, "," ) )
    self.remoteServerList = List.uniqueElements( self.remoteServerList )
    self.compressedConfigurationData = zlib.compress( str( self.remoteCFG ), 9 )

  def loadFile( self, fileName ):
    self.lock()
    try:
      fileCFG = CFG()
      fileCFG.loadFromFile( fileName )
      self.localCFG = self.localCFG.mergeWith( fileCFG )
      self.unlock()
      gLogger.debug( "Configuration file loaded", "'%s'" % fileName )
    except IOError, e:
      self.unlock()
      gLogger.warn( "Can't load a cfg file", "'%s'" % fileName )
      return S_ERROR( "Can't load a cfg file '%s'" % fileName )
    self.sync()
    return S_OK()

  def loadRemoteCFGFromCompressedMem( self, buffer ):
    sUncompressedData = zlib.decompress( buffer )
    self.loadRemoteCFGFromMem( sUncompressedData )

  def loadRemoteCFGFromMem( self, buffer ):
    self.lock()
    self.remoteCFG.loadFromBuffer( buffer )
    self.unlock()
    self.sync()

  def loadConfigurationData( self ):
    name = self.getName()
    self.lock()
    try:
      self.remoteCFG.loadFromFile( "%s/etc/%s.cfg" % ( DIRAC.rootPath, name ) )
    except:
      pass
    self.unlock()
    self.sync()

  def getCommentFromCFG( self, path, cfg = False ):
    if not cfg:
      cfg = self.mergedCFG
    self.dangerZoneStart()
    try:
      levelList = [ level.strip() for level in path.split( "/" ) if level.strip() != "" ]
      for section in levelList[:-1]:
        cfg = cfg[ section ]
      return self.dangerZoneEnd( cfg.getComment( levelList[-1] ) )
    except Exception, e:
      pass
    return self.dangerZoneEnd( None )

  def getSectionsFromCFG( self, path, cfg = False, ordered = False ):
    if not cfg:
      cfg = self.mergedCFG
    self.dangerZoneStart()
    try:
      levelList = [ level.strip() for level in path.split( "/" ) if level.strip() != "" ]
      for section in levelList:
        cfg = cfg[ section ]
      return self.dangerZoneEnd( cfg.listSections( ordered ) )
    except Exception, e:
      pass
    return self.dangerZoneEnd( None )

  def getOptionsFromCFG( self, path, cfg = False, ordered = False ):
    if not cfg:
      cfg = self.mergedCFG
    self.dangerZoneStart()
    try:
      levelList = [ level.strip() for level in path.split( "/" ) if level.strip() != "" ]
      for section in levelList:
        cfg = cfg[ section ]
      return self.dangerZoneEnd( cfg.listOptions( ordered ) )
    except Exception, e:
      pass
    return self.dangerZoneEnd( None )

  def extractOptionFromCFG( self, path, cfg = False ):
    if not cfg:
      cfg = self.mergedCFG
    self.dangerZoneStart()
    try:
      levelList = [ level.strip() for level in path.split( "/" ) if level.strip() != "" ]
      for section in levelList[:-1]:
        cfg = cfg[ section ]
      if levelList[-1] in cfg.listOptions():
        return self.dangerZoneEnd( cfg[ levelList[ -1 ] ] )
    except Exception, e:
      pass
    return self.dangerZoneEnd( None )

  def setOptionInCFG( self, path, value, cfg = False ):
    if not cfg:
      cfg = self.localCFG
    self.dangerZoneStart()
    try:
      levelList = [ level.strip() for level in path.split( "/" ) if level.strip() != "" ]
      for section in levelList[:-1]:
        if section not in cfg.listSections():
          cfg.createNewSection( section )
        cfg = cfg[ section ]
      cfg.setOption( levelList[ -1 ], value )
    finally:
      self.dangerZoneEnd()
    self.sync()

  def deleteOptionInCFG( self, path, value, cfg = False ):
    if not cfg:
      cfg = self.localCFG
    self.dangerZoneStart()
    try:
      levelList = [ level.strip() for level in path.split( "/" ) if level.strip() != "" ]
      for section in levelList[:-1]:
        if section not in cfg.listSections():
          return
        cfg = cfg[ section ]
      cfg.deleteKey( levelList[ -1 ] )
    finally:
      self.dangerZoneEnd()
    self.sync()

  def generateNewVersion( self ):
    self.setVersion( Time.toString() )
    self.sync()
    gLogger.info( "Generated new version %s" % self.getVersion() )

  def setVersion( self, version, cfg = False ):
    if not cfg:
      cfg = self.remoteCFG
    self.setOptionInCFG( "%s/Version" % self.configurationPath,
                                  version,
                                  cfg )

  def getVersion( self, cfg = False ):
    if not cfg:
      cfg = self.remoteCFG
    value = self.extractOptionFromCFG( "%s/Version" % self.configurationPath,
                                        cfg )
    if value:
      return value
    return "0"

  def getName( self ):
    return self.extractOptionFromCFG( "%s/Name" % self.configurationPath,
                                        self.mergedCFG )

  def exportName( self ):
    return self.setOptionInCFG( "%s/Name" % self.configurationPath,
                                self.getName(),
                                self.remoteCFG )
    self.sync()

  def getRefreshTime( self ):
    try:
      return int( self.extractOptionFromCFG( "%s/RefreshTime" % self.configurationPath,
                                        self.mergedCFG ) )
    except:
      return 300

  def getPropagationTime( self ):
    try:
      return int( self.extractOptionFromCFG( "%s/PropagationTime" % self.configurationPath,
                                        self.mergedCFG ) )
    except:
      return 300

  def getSlavesGraceTime( self ):
    try:
      return int( self.extractOptionFromCFG( "%s/SlavesGraceTime" % self.configurationPath,
                                        self.mergedCFG ) )
    except:
      return 600

  def getAutoPublish( self ):
    value = self.extractOptionFromCFG( "%s/AutoPublish" % self.configurationPath,
                                        self.localCFG )
    if value and value.lower() in ( "no", "false", "n" ):
        return False
    else:
        return True

  def getServers( self ):
    return list( self.remoteServerList )

  def getConfigurationGateway( self ):
    return self.extractOptionFromCFG( "/DIRAC/Gateway",
                                        self.localCFG )

  def setServers( self, sServers ):
    self.setOptionInCFG( "%s/Servers" % self.configurationPath,
                                  sServers,
                                  self.remoteCFG )
    self.sync()

  def deleteLocalOption( self, optionPath ):
    self.deleteOptionInCFG( optionPath,
                                        self.localCFG )

  def getMasterServer( self ):
    return self.extractOptionFromCFG( "%s/MasterServer" % self.configurationPath,
                                      self.remoteCFG )

  def setMasterServer( self, sURL ):
    self.setOptionInCFG( "%s/MasterServer" % self.configurationPath,
                         sURL,
                         self.remoteCFG )
    self.sync()

  def getCompressedData( self ):
    return self.compressedConfigurationData

  def isMaster( self ):
    value = self.extractOptionFromCFG( "%s/Master" % self.configurationPath,
                                            self.localCFG )
    if value and value.lower() in ( "yes", "true", "y" ):
        return True
    else:
        return False

  def getServicesPath( self ):
    return "/Services"

  def setAsService( self ):
    self.isService = True

  def isService( self ):
    return self.isService

  def useServerCertificate( self ):
    value = self.extractOptionFromCFG( "/DIRAC/Security/UseServerCertificate" )
    if value and value.lower() in ( "y", "yes", "true" ):
      return True
    return False


  def dumpLocalCFGToFile( self, fileName ):
    try:
      fd = open( fileName, "w" )
      fd.write( str( self.localCFG ) )
      fd.close()
      gLogger.verbose( "Configuration file dumped", "'%s'" % fileName )
    except IOError, e:
      gLogger.error( "Can't dump cfg file", "'%s'" % fileName )
      return S_ERROR( "Can't dump cfg file '%s'" % fileName )
    return S_OK()

  def getMergedCFGAsString( self ):
    return str( self.mergedCFG )

  def dumpRemoteCFGToFile( self, fileName ):
    fd = open( fileName, "w" )
    fd.write( str( self.remoteCFG ) )
    fd.close()

  def __backupCurrentConfiguration( self, backupName = False ):
    if not backupName:
      backupName = self.getVersion()
    configurationFilename = "%s.cfg" % self.getName()
    configurationFile = "%s/etc/%s" % ( DIRAC.rootPath, configurationFilename )
    today = Time.date()
    backupPath = "%s/%s/%s" % ( self.getBackupDir(), today.year, today.month )
    try:
      os.makedirs( backupPath )
    except:
      pass
    backupFile = "%s/%s" % ( backupPath, configurationFilename.replace( ".cfg", ".%s.zip" % backupName ) )
    if os.path.isfile( configurationFile ):
      gLogger.info( "Making a backup of configuration in %s" % backupFile )
      try:
        zf = zipfile.ZipFile( backupFile, "w", zipfile.ZIP_DEFLATED );
        zf.write( configurationFile, "%s.backup.%s" % ( os.path.split( configurationFile )[1], backupName )  )
        zf.close()
      except Exception, v:
        gLogger.exception()
        gLogger.error( "Cannot backup configuration data file",
                     "file %s" % backupFile )
    else:
      gLogger.warn( "CS data file does not exist", configurationFile )

  def writeRemoteConfigurationToDisk( self, backupName = False ):
    configurationFile = "%s/etc/%s.cfg" % ( DIRAC.rootPath, self.getName() )
    try:
      fd = open( configurationFile, "w" )
      fd.write( str( self.remoteCFG ) )
      fd.close()
    except:
      gLogger.fatal( "Cannot write new configuration to disk!",
                     "file %s" % configurationFile )
      return S_ERROR( "Can't write cs file %s!: %s" % ( configurationFile, str( e ) ) )
    self.__backupCurrentConfiguration( backupName )
    return S_OK()

  def lock(self):
    """
    Locks Event to prevent further threads from reading.
    Stops current thread until no other thread is accessing.
    PRIVATE USE
    """
    self.threadingEvent.clear()
    while self.runningThreadsNumber > 0:
      time.sleep( 0.1 )

  def unlock(self):
    """
    Unlocks Event.
    PRIVATE USE
    """
    self.threadingEvent.set()

  def dangerZoneStart(self):
    """
    Start of danger zone. This danger zone may be or may not be a mutual exclusion zone.
    Counter is maintained to know how many threads are inside and be able to enable and disable mutual exclusion.
    PRIVATE USE
    """
    self.threadingEvent.wait()
    self.threadingLock.acquire()
    self.runningThreadsNumber  += 1
    self.threadingLock.release()


  def dangerZoneEnd( self, returnValue = None ):
    """
    End of danger zone.
    PRIVATE USE
    """
    self.threadingLock.acquire()
    self.runningThreadsNumber -= 1
    self.threadingLock.release()
    return returnValue
