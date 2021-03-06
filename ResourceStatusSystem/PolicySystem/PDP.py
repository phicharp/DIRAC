# $HeadURL $
''' PDP

  PolicyDecissionPoint

'''

import datetime

from DIRAC                                                import gLogger 
from DIRAC.ResourceStatusSystem.PolicySystem              import Status
from DIRAC.ResourceStatusSystem.Utilities.InfoGetter      import InfoGetter
from DIRAC.ResourceStatusSystem.PolicySystem.PolicyCaller import PolicyCaller
from DIRAC.ResourceStatusSystem.Command.CommandCaller     import CommandCaller

__RCSID__  = '$Id: $'

class PDP:
  """
    The PDP (Policy Decision Point) module is used to:
    1. Decides which policies have to be applied.
    2. Invokes an evaluation of the policies, and returns the result (to a PEP)
  """

  def __init__( self, **clients ):
    '''
      Constructor. Defines members that will be used later on.
    '''
    
    cc                  = CommandCaller()
    self.clients        = clients
    self.pCaller        = PolicyCaller( cc, **clients )
    self.iGetter        = InfoGetter()

    self.__granularity  = None
    self.__name         = None
    self.__statusType   = None
    self.__status       = None
    self.__formerStatus = None
    self.__reason       = None
    self.__siteType     = None
    self.__serviceType  = None
    self.__resourceType = None
    self.__useNewRes    = None
        

  def setup( self, granularity = None, name = None, statusType = None,
             status = None, formerStatus = None, reason = None, siteType = None,
             serviceType = None, resourceType = None, useNewRes = False ):
    """
    PDP (Policy Decision Point) initialization

    :params:
      :attr:`granularity`: string - a ValidElement
      :attr:`name`: string - name (e.g. of a site)
      :attr:`status`: string - status
      :attr:`formerStatus`: string - former status
      :attr:`reason`: string - optional reason for last status change
      :attr:`siteType`: string - optional site type
      :attr:`serviceType`: string - optional service type
      :attr:`resourceType`: string - optional resource type
    """

    self.__granularity  = granularity
    self.__name         = name
    self.__statusType   = statusType
    self.__status       = status
    self.__formerStatus = formerStatus
    self.__reason       = reason
    self.__siteType     = siteType
    self.__serviceType  = serviceType
    self.__resourceType = resourceType
    self.__useNewRes    = useNewRes



################################################################################

  def takeDecision( self, policyIn = None, argsIn = None, knownInfo = None ):
    """ PDP MAIN FUNCTION

        decides policies that have to be applied, based on

        __granularity,

        __name,

        __status,

        __formerStatus

        __reason

        If more than one policy is evaluated, results are combined.

        Logic for combination: a conservative approach is followed
        (i.e. if a site should be banned for at least one policy, that's what is returned)

        returns:

          { 'PolicyType': a policyType (in a string),
            'Action': True|False,
            'Status': 'Active'|'Probing'|'Banned',
            'Reason': a reason
            'EndDate: datetime.datetime (in a string)}
    """

    polToEval = self.iGetter.getInfoToApply( ( 'policy', 'policyType' ),
                                        granularity  = self.__granularity,
                                        statusType   = self.__statusType,
                                        status       = self.__status,
                                        formerStatus = self.__formerStatus,
                                        siteType     = self.__siteType,
                                        serviceType  = self.__serviceType,
                                        resourceType = self.__resourceType,
                                        useNewRes    = self.__useNewRes )

    policyType = polToEval[ 'PolicyType' ] # type: generator

    if policyIn:
      # Only the policy provided will be evaluated
      # FIXME: Check that the policies are valid.
      singlePolicyResults = policyIn.evaluate()

    else:
      singlePolicyResults = self._invocation( self.__granularity,
                                              self.__name, self.__status, policyIn,
                                              argsIn, polToEval['Policies'] )

    policyCombinedResults = self._policyCombination( singlePolicyResults )

    if policyCombinedResults == {}:
      policyCombinedResults[ 'Action' ]     = False
      policyCombinedResults[ 'Reason' ]     = 'No policy results'
      policyCombinedResults[ 'PolicyType' ] = policyType

    if policyCombinedResults.has_key( 'Status' ):
      newstatus = policyCombinedResults[ 'Status' ]

      if newstatus != self.__status: # Policies satisfy
        newPolicyType = self.iGetter.getNewPolicyType( self.__granularity, newstatus )
        policyType    = set( policyType ) & set( newPolicyType )
        
        policyCombinedResults[ 'Action' ] = True

      else:                          # Policies does not satisfy
        policyCombinedResults[ 'Action' ] = False

      policyCombinedResults[ 'PolicyType' ] = policyType

    return { 'SinglePolicyResults'  : singlePolicyResults,
             'PolicyCombinedResult' : policyCombinedResults }

################################################################################

  def _invocation( self, granularity, name, status, policy, args, policies ):
    '''
      One by one, use the PolicyCaller to invoke the policies, and putting
      their results in `policyResults`. When the status is `Unknown`, invokes
      `self.__useOldPolicyRes`. Always returns a list, possibly empty.
    '''

    policyResults = []

    for pol in policies:
      
      pName     = pol[ 'Name' ]
      pModule   = pol[ 'Module' ]
      extraArgs = pol[ 'args' ]
      commandIn = pol[ 'commandIn' ]
      
      res = self.pCaller.policyInvocation( granularity = granularity, name = name,
                                           status = status, policy = policy, 
                                           args = args, pName = pName,
                                           pModule = pModule, extraArgs = extraArgs, 
                                           commandIn = commandIn )

      # If res is empty, return immediately
      if not res: 
        return policyResults

      if not res.has_key( 'Status' ):
        print('\n\n Policy result ' + str(res) + ' does not return "Status"\n\n')
        raise TypeError

      # Else
      if res[ 'Status' ] == 'Unknown':
        res = self.__useOldPolicyRes( name = name, policyName = pName )

      if res[ 'Status' ] not in ( 'Error', 'Unknown' ):
        policyResults.append( res )
      else:
        gLogger.warn( res )      
      
    return policyResults

################################################################################

  def _policyCombination( self, pol_results ):
    '''
    INPUT: list type
    OUTPUT: dict type
    * Compute a new status, and store it in variable newStatus, of type integer.
    * Make a list of policies that have the worst result.
    * Concatenate the Reason fields
    * Take the first EndDate field that exists (FIXME: Do something more clever)
    * Finally, return the result
    '''
    if pol_results == []: 
      return {}

    pol_results.sort( key=Status.value_of_policy )
    newStatus = -1 # First, set an always invalid status

    try:
      # We are in a special status, maybe forbidden transitions
      _prio, access_list, gofun = Status.statesInfo[ self.__status ]
      if access_list != set():
        # Restrictions on transitions, checking if one is suitable:
        for polRes in pol_results:
          if Status.value_of_policy( polRes ) in access_list:
            newStatus = Status.value_of_policy( polRes )
            break

        # No status from policies suitable, applying stategy and
        # returning result.
        if newStatus == -1:
          newStatus = gofun( access_list )
          return { 'Status': Status.status_of_value( newStatus ),
                   'Reason': 'Status forced by PDP' }

      else:
        # Special Status, but no restriction on transitions
        newStatus = Status.value_of_policy( pol_results[ 0 ] )

    except KeyError:
      # We are in a "normal" status: All transitions are possible.
      newStatus = Status.value_of_policy( pol_results[ 0 ] )

    # At this point, a new status has been chosen. newStatus is an
    # integer.

    worstResults = [ p for p in pol_results
                     if Status.value_of_policy( p ) == newStatus ]

    # Concatenate reasons
    def getReason( pol ):
      try:
        res = pol[ 'Reason' ]
      except KeyError:
        res = ''
      return res

    worstResultsReasons = [ getReason( p ) for p in worstResults ]

    def catRes( xVal, yVal ):
      '''
        Concatenate xVal and yVal.
      '''
      if xVal and yVal : 
        return xVal + ' |###| ' + yVal
      elif xVal or yVal:
        if xVal: 
          return xVal
        else: 
          return yVal
      else: 
        return ''

    concatenatedRes = reduce( catRes, worstResultsReasons, '' )

    # Handle EndDate
    endDatePolicies = [ p for p in worstResults if p.has_key( 'EndDate' ) ]

    # Building and returning result
    res = {}
    res[ 'Status' ] = Status.status_of_value( newStatus )
    if concatenatedRes != '': 
      res[ 'Reason' ]  = concatenatedRes
    if endDatePolicies != []: 
      res[ 'EndDate' ] = endDatePolicies[ 0 ][ 'EndDate' ]
    return res

################################################################################

  def __useOldPolicyRes( self, name, policyName ):
    '''
     Use the RSS Service to get an old policy result.
     If such result is older than 2 hours, it returns {'Status':'Unknown'}
    '''
    res = self.clients[ 'ResourceManagementClient' ].getPolicyResult( name = name, policyName = policyName )
    
    if not res[ 'OK' ]:
      return { 'Status' : 'Unknown' }
    
    res = res[ 'Value' ]

    if res == []:
      return { 'Status' : 'Unknown' }

    res = res[ 0 ]

    oldStatus     = res[ 5 ]
    oldReason     = res[ 6 ]
    lastCheckTime = res[ 8 ]

    if ( lastCheckTime + datetime.timedelta(hours = 2) ) < datetime.datetime.utcnow():
      return { 'Status' : 'Unknown' }

    result = {}

    result[ 'Status' ]     = oldStatus
    result[ 'Reason' ]     = oldReason
    result[ 'OLD' ]        = True
    result[ 'PolicyName' ] = policyName

    return result

################################################################################
#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF