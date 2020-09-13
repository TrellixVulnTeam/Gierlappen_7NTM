import re

from mongoengine import connect
from pycoshark.mongomodels import Commit, File, CodeEntityState, FileAction, Issue, IssueSystem, Project, VCSSystem
from pycoshark.utils import java_filename_filter, jira_is_resolved_and_fixed

from pydriller import GitRepository
from pydriller.domain.commit import ModificationType

from util.metrics import get_warning_density, get_warning_list


# Static Source Code Metrics from Sourcemeter homepage https://www.sourcemeter.com/resources/java/ 2018-07-24
STATIC = ['PDA', 'LOC', 'CLOC', 'PUA', 'McCC', 'LLOC', 'LDC', 'NOS', 'MISM', 'CCL', 'TNOS', 'TLLOC',
          'NLE', 'CI', 'HPL', 'MI', 'HPV', 'CD', 'NOI', 'NUMPAR', 'MISEI', 'CC', 'LLDC', 'NII', 'CCO', 'CLC', 'TCD', 'NL', 'TLOC', 'CLLC', 'TCLOC', 'MIMS', 'HDIF', 'DLOC', 'NLM', 'DIT', 'NPA', 'TNLPM',
          'TNLA', 'NLA', 'AD', 'TNLPA', 'NM', 'TNG', 'NLPM', 'TNM', 'NOC', 'NOD', 'NOP', 'NLS', 'NG', 'TNLG', 'CBOI', 'RFC', 'NLG', 'TNLS', 'TNA', 'NLPA', 'NOA', 'WMC', 'NPM', 'TNPM', 'TNS', 'NA', 'LCOM5', 'NS', 'CBO', 'TNLM', 'TNPA']


PMD_RULES = [{'type': 'Basic Rules', 'rule': 'Avoid Branching Statement As Last In Loop', 'abbrev': 'PMD_ABSALIL', 'severity': 'Major'}, {'type': 'Basic Rules', 'rule': 'Avoid Decimal Literals In Big Decimal Constructor', 'abbrev': 'PMD_ADLIBDC', 'severity': 'Critical'}, {'type': 'Basic Rules', 'rule': 'Avoid Multiple Unary Operators', 'abbrev': 'PMD_AMUO', 'severity': 'Major'}, {'type': 'Basic Rules', 'rule': 'Avoid Thread Group', 'abbrev': 'PMD_ATG', 'severity': 'Critical'}, {'type': 'Basic Rules', 'rule': 'Avoid Using Hard Coded IP', 'abbrev': 'PMD_AUHCIP', 'severity': 'Major'}, {'type': 'Basic Rules', 'rule': 'Avoid Using Octal Values', 'abbrev': 'PMD_AUOV', 'severity': 'Critical'}, {'type': 'Basic Rules', 'rule': 'Big Integer Instantiation', 'abbrev': 'PMD_BII', 'severity': 'Minor'}, {'type': 'Basic Rules', 'rule': 'Boolean Instantiation', 'abbrev': 'PMD_BI', 'severity': 'Minor'}, {'type': 'Basic Rules', 'rule': 'Broken Null Check', 'abbrev': 'PMD_BNC', 'severity': 'Critical'}, {'type': 'Basic Rules', 'rule': 'Check Result Set', 'abbrev': 'PMD_CRS', 'severity': 'Critical'}, {'type': 'Basic Rules', 'rule': 'Check Skip Result', 'abbrev': 'PMD_CSR', 'severity': 'Critical'}, {'type': 'Basic Rules', 'rule': 'Class Cast Exception With To Array', 'abbrev': 'PMD_CCEWTA', 'severity': 'Critical'}, {'type': 'Basic Rules', 'rule': 'Collapsible If Statements', 'abbrev': 'PMD_CIS', 'severity': 'Minor'}, {'type': 'Basic Rules', 'rule': 'Dont Call Thread Run', 'abbrev': 'PMD_DCTR', 'severity': 'Critical'}, {'type': 'Basic Rules', 'rule': 'Dont Use Float Type For Loop Indices', 'abbrev': 'PMD_DUFTFLI', 'severity': 'Critical'}, {'type': 'Basic Rules', 'rule': 'Double Checked Locking', 'abbrev': 'PMD_DCL', 'severity': 'Critical'}, {'type': 'Basic Rules', 'rule': 'Empty Catch Block', 'abbrev': 'PMD_ECB', 'severity': 'Critical'}, {'type': 'Basic Rules', 'rule': 'Empty Finally Block', 'abbrev': 'PMD_EFB', 'severity': 'Minor'}, {'type': 'Basic Rules', 'rule': 'Empty If Stmt', 'abbrev': 'PMD_EIS', 'severity': 'Major'}, {'type': 'Basic Rules', 'rule': 'Empty Statement Block', 'abbrev': 'PMD_EmSB', 'severity': 'Minor'}, {'type': 'Basic Rules', 'rule': 'Empty Statement Not In Loop', 'abbrev': 'PMD_ESNIL', 'severity': 'Minor'}, {'type': 'Basic Rules', 'rule': 'Empty Static Initializer', 'abbrev': 'PMD_ESI', 'severity': 'Minor'}, {'type': 'Basic Rules', 'rule': 'Empty Switch Statements', 'abbrev': 'PMD_ESS', 'severity': 'Major'}, {'type': 'Basic Rules', 'rule': 'Empty Synchronized Block', 'abbrev': 'PMD_ESB', 'severity': 'Major'}, {'type': 'Basic Rules', 'rule': 'Empty Try Block', 'abbrev': 'PMD_ETB', 'severity': 'Major'}, {'type': 'Basic Rules', 'rule': 'Empty While Stmt', 'abbrev': 'PMD_EWS', 'severity': 'Critical'}, {'type': 'Basic Rules', 'rule': 'Extends Object', 'abbrev': 'PMD_EO', 'severity': 'Minor'}, {'type': 'Basic Rules', 'rule': 'For Loop Should Be While Loop', 'abbrev': 'PMD_FLSBWL', 'severity': 'Minor'}, {'type': 'Basic Rules', 'rule': 'Jumbled Incrementer', 'abbrev': 'PMD_JI', 'severity': 'Critical'}, {'type': 'Basic Rules', 'rule': 'Misplaced Null Check', 'abbrev': 'PMD_MNC', 'severity': 'Critical'}, {'type': 'Basic Rules', 'rule': 'Override Both Equals And Hashcode', 'abbrev': 'PMD_OBEAH', 'severity': 'Critical'}, {'type': 'Basic Rules', 'rule': 'Return From Finally Block', 'abbrev': 'PMD_RFFB', 'severity': 'Critical'}, {'type': 'Basic Rules', 'rule': 'Unconditional If Statement', 'abbrev': 'PMD_UIS', 'severity': 'Major'}, {'type': 'Basic Rules', 'rule': 'Unnecessary Conversion Temporary', 'abbrev': 'PMD_UCT', 'severity': 'Minor'}, {'type': 'Basic Rules', 'rule': 'Unused Null Check In Equals', 'abbrev': 'PMD_UNCIE', 'severity': 'Critical'}, {'type': 'Basic Rules', 'rule': 'Useless Operation On Immutable', 'abbrev': 'PMD_UOOI', 'severity': 'Critical'}, {'type': 'Basic Rules', 'rule': 'Useless Overriding Method', 'abbrev': 'PMD_UOM', 'severity': 'Minor'}, {'type': 'Brace Rules', 'rule': 'For Loops Must Use Braces', 'abbrev': 'PMD_FLMUB', 'severity': 'Minor'}, {'type': 'Brace Rules', 'rule': 'If Else Stmts Must Use Braces', 'abbrev': 'PMD_IESMUB', 'severity': 'Minor'}, {'type': 'Brace Rules', 'rule': 'If Stmts Must Use Braces', 'abbrev': 'PMD_ISMUB', 'severity': 'Minor'}, {'type': 'Brace Rules', 'rule': 'While Loops Must Use Braces', 'abbrev': 'PMD_WLMUB', 'severity': 'Minor'}, {'type': 'Clone Implementation Rules', 'rule': 'Clone Throws Clone Not Supported Exception', 'abbrev': 'PMD_CTCNSE', 'severity': 'Major'}, {'type': 'Clone Implementation Rules', 'rule': 'Proper Clone Implementation', 'abbrev': 'PMD_PCI', 'severity': 'Critical'}, {'type': 'Controversial Rules', 'rule': 'Assignment In Operand', 'abbrev': 'PMD_AIO', 'severity': 'Minor'}, {'type': 'Controversial Rules', 'rule': 'Avoid Accessibility Alteration', 'abbrev': 'PMD_AAA', 'severity': 'Major'}, {'type': 'Controversial Rules', 'rule': 'Avoid Prefixing Method Parameters', 'abbrev': 'PMD_APMP', 'severity': 'Minor'}, {'type': 'Controversial Rules', 'rule': 'Avoid Using Native Code', 'abbrev': 'PMD_AUNC', 'severity': 'Major'}, {'type': 'Controversial Rules', 'rule': 'Default Package', 'abbrev': 'PMD_DP', 'severity': 'Minor'}, {'type': 'Controversial Rules', 'rule': 'Do Not Call Garbage Collection Explicitly', 'abbrev': 'PMD_DNCGCE', 'severity': 'Major'}, {'type': 'Controversial Rules', 'rule': 'Dont Import Sun', 'abbrev': 'PMD_DIS', 'severity': 'Major'}, {'type': 'Controversial Rules', 'rule': 'One Declaration Per Line', 'abbrev': 'PMD_ODPL', 'severity': 'Minor'}, {'type': 'Controversial Rules', 'rule': 'Suspicious Octal Escape', 'abbrev': 'PMD_SOE', 'severity': 'Major'}, {'type': 'Controversial Rules', 'rule': 'Unnecessary Constructor', 'abbrev': 'PMD_UC', 'severity': 'Minor'}, {'type': 'Design Rules', 'rule': 'Abstract Class Without Abstract Method', 'abbrev': 'PMD_ACWAM', 'severity': 'Minor'}, {'type': 'Design Rules', 'rule': 'Abstract Class Without Any Method', 'abbrev': 'PMD_AbCWAM', 'severity': 'Minor'}, {'type': 'Design Rules', 'rule': 'Assignment To Non Final Static', 'abbrev': 'PMD_ATNFS', 'severity': 'Critical'}, {'type': 'Design Rules', 'rule': 'Avoid Constants Interface', 'abbrev': 'PMD_ACI', 'severity': 'Minor'}, {'type': 'Design Rules', 'rule': 'Avoid Instanceof Checks In Catch Clause', 'abbrev': 'PMD_AICICC', 'severity': 'Major'}, {'type': 'Design Rules', 'rule': 'Avoid Protected Field In Final Class', 'abbrev': 'PMD_APFIFC', 'severity': 'Minor'}, {'type': 'Design Rules', 'rule': 'Avoid Protected Method In Final Class Not Extending', 'abbrev': 'PMD_APMIFCNE', 'severity': 'Minor'}, {'type': 'Design Rules', 'rule': 'Avoid Reassigning Parameters', 'abbrev': 'PMD_ARP', 'severity': 'Minor'}, {'type': 'Design Rules', 'rule': 'Avoid Synchronized At Method Level', 'abbrev': 'PMD_ASAML', 'severity': 'Minor'}, {'type': 'Design Rules', 'rule': 'Bad Comparison', 'abbrev': 'PMD_BC', 'severity': 'Critical'}, {'type': 'Design Rules', 'rule': 'Class With Only Private Constructors Should Be Final', 'abbrev': 'PMD_CWOPCSBF', 'severity': 'Minor'}, {'type': 'Design Rules', 'rule': 'Close Resource', 'abbrev': 'PMD_ClR', 'severity': 'Critical'}, {'type': 'Design Rules', 'rule': 'Constructor Calls Overridable Method', 'abbrev': 'PMD_CCOM', 'severity': 'Critical'}, {'type': 'Design Rules', 'rule': 'Default Label Not Last In Switch Stmt', 'abbrev': 'PMD_DLNLISS', 'severity': 'Minor'}, {'type': 'Design Rules', 'rule': 'Empty Method In Abstract Class Should Be Abstract', 'abbrev': 'PMD_EMIACSBA', 'severity': 'Major'}, {'type': 'Design Rules', 'rule': 'Equals Null', 'abbrev': 'PMD_EN', 'severity': 'Critical'}, {'type': 'Design Rules', 'rule': 'Field Declarations Should Be At Start Of Class', 'abbrev': 'PMD_FDSBASOC', 'severity': 'Minor'}, {'type': 'Design Rules', 'rule': 'Final Field Could Be Static', 'abbrev': 'PMD_FFCBS', 'severity': 'Minor'}, {'type': 'Design Rules', 'rule': 'Idempotent Operations', 'abbrev': 'PMD_IO', 'severity': 'Major'}, {'type': 'Design Rules', 'rule': 'Immutable Field', 'abbrev': 'PMD_IF', 'severity': 'Minor'}, {'type': 'Design Rules', 'rule': 'Instantiation To Get Class', 'abbrev': 'PMD_ITGC', 'severity': 'Major'}, {'type': 'Design Rules', 'rule': 'Logic Inversion', 'abbrev': 'PMD_LI', 'severity': 'Minor'}, {'type': 'Design Rules', 'rule': 'Missing Break In Switch', 'abbrev': 'PMD_MBIS', 'severity': 'Critical'}, {'type': 'Design Rules', 'rule': 'Missing Static Method In Non Instantiatable Class', 'abbrev': 'PMD_MSMINIC', 'severity': 'Minor'}, {'type': 'Design Rules', 'rule': 'Non Case Label In Switch Statement', 'abbrev': 'PMD_NCLISS', 'severity': 'Critical'}, {'type': 'Design Rules', 'rule': 'Non Static Initializer', 'abbrev': 'PMD_NSI', 'severity': 'Critical'}, {'type': 'Design Rules', 'rule': 'Non Thread Safe Singleton', 'abbrev': 'PMD_NTSS', 'severity': 'Critical'}, {'type': 'Design Rules', 'rule': 'Optimizable To Array Call', 'abbrev': 'PMD_OTAC', 'severity': 'Major'}, {'type': 'Design Rules', 'rule': 'Position Literals First In Case Insensitive Comparisons', 'abbrev': 'PMD_PLFICIC', 'severity': 'Critical'}, {'type': 'Design Rules', 'rule': 'Position Literals First In Comparisons', 'abbrev': 'PMD_PLFIC', 'severity': 'Critical'}, {'type': 'Design Rules', 'rule': 'Preserve Stack Trace', 'abbrev': 'PMD_PST', 'severity': 'Major'}, {'type': 'Design Rules', 'rule': 'Return Empty Array Rather Than Null', 'abbrev': 'PMD_REARTN', 'severity': 'Major'}, {'type': 'Design Rules', 'rule': 'Simple Date Format Needs Locale', 'abbrev': 'PMD_SDFNL', 'severity': 'Minor'}, {'type': 'Design Rules', 'rule': 'Simplify Boolean Expressions', 'abbrev': 'PMD_SBE', 'severity': 'Minor'}, {'type': 'Design Rules', 'rule': 'Simplify Boolean Returns', 'abbrev': 'PMD_SBR', 'severity': 'Minor'}, {'type': 'Design Rules', 'rule': 'Simplify Conditional', 'abbrev': 'PMD_SC', 'severity': 'Minor'}, {'type': 'Design Rules', 'rule': 'Singular Field', 'abbrev': 'PMD_SF', 'severity': 'Major'}, {'type': 'Design Rules', 'rule': 'Switch Stmts Should Have Default', 'abbrev': 'PMD_SSSHD', 'severity': 'Major'}, {'type': 'Design Rules', 'rule': 'Too Few Branches For ASwitch Statement', 'abbrev': 'PMD_TFBFASS', 'severity': 'Minor'}, {'type': 'Design Rules', 'rule': 'Uncommented Empty Constructor', 'abbrev': 'PMD_UEC', 'severity': 'Minor'}, {'type': 'Design Rules', 'rule': 'Uncommented Empty Method', 'abbrev': 'PMD_UEM', 'severity': 'Minor'}, {'type': 'Design Rules', 'rule': 'Unnecessary Local Before Return', 'abbrev': 'PMD_ULBR', 'severity': 'Minor'}, {'type': 'Design Rules', 'rule': 'Unsynchronized Static Date Formatter', 'abbrev': 'PMD_USDF', 'severity': 'Critical'}, {'type': 'Design Rules', 'rule': 'Use Collection Is Empty', 'abbrev': 'PMD_UCIE', 'severity': 'Major'}, {'type': 'Design Rules', 'rule': 'Use Locale With Case Conversions', 'abbrev': 'PMD_ULWCC', 'severity': 'Critical'}, {'type': 'Design Rules', 'rule': 'Use Notify All Instead Of Notify', 'abbrev': 'PMD_UNAION', 'severity': 'Critical'}, {'type': 'Design Rules', 'rule': 'Use Varargs', 'abbrev': 'PMD_UV', 'severity': 'Minor'}, {'type': 'Finalizer Rules', 'rule': 'Avoid Calling Finalize', 'abbrev': 'PMD_ACF', 'severity': 'Major'}, {'type': 'Finalizer Rules', 'rule': 'Empty Finalizer', 'abbrev': 'PMD_EF', 'severity': 'Minor'}, {'type': 'Finalizer Rules', 'rule': 'Finalize Does Not Call Super Finalize', 'abbrev': 'PMD_FDNCSF', 'severity': 'Critical'}, {'type': 'Finalizer Rules', 'rule': 'Finalize Only Calls Super Finalize', 'abbrev': 'PMD_FOCSF', 'severity': 'Minor'}, {'type': 'Finalizer Rules', 'rule': 'Finalize Overloaded', 'abbrev': 'PMD_FO', 'severity': 'Critical'}, {'type': 'Finalizer Rules', 'rule': 'Finalize Should Be Protected', 'abbrev': 'PMD_FSBP', 'severity': 'Critical'}, {'type': 'Import Statement Rules', 'rule': 'Dont Import Java Lang', 'abbrev': 'PMD_DIJL', 'severity': 'Minor'}, {'type': 'Import Statement Rules', 'rule': 'Duplicate Imports', 'abbrev': 'PMD_DI', 'severity': 'Minor'}, {'type': 'Import Statement Rules', 'rule': 'Import From Same Package', 'abbrev': 'PMD_IFSP', 'severity': 'Minor'}, {'type': 'Import Statement Rules', 'rule': 'Too Many Static Imports', 'abbrev': 'PMD_TMSI', 'severity': 'Major'}, {'type': 'Import Statement Rules', 'rule': 'Unnecessary Fully Qualified Name', 'abbrev': 'PMD_UFQN', 'severity': 'Minor'}, {'type': 'J2EE Rules', 'rule': 'Do Not Call System Exit', 'abbrev': 'PMD_DNCSE', 'severity': 'Critical'}, {'type': 'J2EE Rules', 'rule': 'Local Home Naming Convention', 'abbrev': 'PMD_LHNC', 'severity': 'Major'}, {'type': 'J2EE Rules', 'rule': 'Local Interface Session Naming Convention', 'abbrev': 'PMD_LISNC', 'severity': 'Major'}, {'type': 'J2EE Rules', 'rule': 'MDBAnd Session Bean Naming Convention', 'abbrev': 'PMD_MDBASBNC', 'severity': 'Major'}, {'type': 'J2EE Rules', 'rule': 'Remote Interface Naming Convention', 'abbrev': 'PMD_RINC', 'severity': 'Major'}, {'type': 'J2EE Rules', 'rule': 'Remote Session Interface Naming Convention', 'abbrev': 'PMD_RSINC', 'severity': 'Major'}, {'type': 'J2EE Rules', 'rule': 'Static EJBField Should Be Final', 'abbrev': 'PMD_SEJBFSBF', 'severity': 'Critical'}, {'type': 'JUnit Rules', 'rule': 'JUnit Assertions Should Include Message', 'abbrev': 'PMD_JUASIM', 'severity': 'Minor'}, {'type': 'JUnit Rules', 'rule': 'JUnit Spelling', 'abbrev': 'PMD_JUS', 'severity': 'Critical'}, {'type': 'JUnit Rules', 'rule': 'JUnit Static Suite', 'abbrev': 'PMD_JUSS', 'severity': 'Critical'}, {'type': 'JUnit Rules', 'rule': 'JUnit Test Contains Too Many Asserts', 'abbrev': 'PMD_JUTCTMA', 'severity': 'Minor'}, {'type': 'JUnit Rules', 'rule': 'JUnit Tests Should Include Assert', 'abbrev': 'PMD_JUTSIA', 'severity': 'Major'}, {'type': 'JUnit Rules', 'rule': 'Simplify Boolean Assertion', 'abbrev': 'PMD_SBA', 'severity': 'Minor'}, {'type': 'JUnit Rules', 'rule': 'Test Class Without Test Cases', 'abbrev': 'PMD_TCWTC', 'severity': 'Minor'}, {'type': 'JUnit Rules', 'rule': 'Unnecessary Boolean Assertion', 'abbrev': 'PMD_UBA', 'severity': 'Minor'}, {'type': 'JUnit Rules', 'rule': 'Use Assert Equals Instead Of Assert True', 'abbrev': 'PMD_UAEIOAT', 'severity': 'Major'}, {'type': 'JUnit Rules', 'rule': 'Use Assert Null Instead Of Assert True', 'abbrev': 'PMD_UANIOAT', 'severity': 'Minor'}, {'type': 'JUnit Rules', 'rule': 'Use Assert Same Instead Of Assert True', 'abbrev': 'PMD_UASIOAT', 'severity': 'Minor'}, {'type': 'JUnit Rules', 'rule': 'Use Assert True Instead Of Assert Equals', 'abbrev': 'PMD_UATIOAE', 'severity': 'Minor'}, {'type': 'Jakarta Commons Logging Rules', 'rule': 'Guard Debug Logging', 'abbrev': 'PMD_GDL', 'severity': 'Major'}, {'type': 'Jakarta Commons Logging Rules', 'rule': 'Guard Log Statement', 'abbrev': 'PMD_GLS', 'severity': 'Minor'}, {'type': 'Jakarta Commons Logging Rules', 'rule': 'Proper Logger', 'abbrev': 'PMD_PL', 'severity': 'Minor'}, {'type': 'Jakarta Commons Logging Rules', 'rule': 'Use Correct Exception Logging', 'abbrev': 'PMD_UCEL', 'severity': 'Major'}, {'type': 'Java Logging Rules', 'rule': 'Avoid Print Stack Trace', 'abbrev': 'PMD_APST', 'severity': 'Major'}, {'type': 'Java Logging Rules', 'rule': 'Guard Log Statement Java Util', 'abbrev': 'PMD_GLSJU', 'severity': 'Minor'}, {'type': 'Java Logging Rules', 'rule': 'Logger Is Not Static Final', 'abbrev': 'PMD_LINSF', 'severity': 'Minor'}, {'type': 'Java Logging Rules', 'rule': 'More Than One Logger', 'abbrev': 'PMD_MTOL', 'severity': 'Major'}, {'type': 'Java Logging Rules', 'rule': 'System Println', 'abbrev': 'PMD_SP', 'severity': 'Major'}, {'type': 'JavaBean Rules', 'rule': 'Missing Serial Version UID', 'abbrev': 'PMD_MSVUID', 'severity': 'Major'}, {'type': 'Naming Rules', 'rule': 'Avoid Dollar Signs', 'abbrev': 'PMD_ADS', 'severity': 'Minor'}, {'type': 'Naming Rules', 'rule': 'Avoid Field Name Matching Method Name', 'abbrev': 'PMD_AFNMMN', 'severity': 'Minor'}, {'type': 'Naming Rules', 'rule': 'Avoid Field Name Matching Type Name', 'abbrev': 'PMD_AFNMTN', 'severity': 'Minor'}, {'type': 'Naming Rules', 'rule': 'Boolean Get Method Name', 'abbrev': 'PMD_BGMN', 'severity': 'Minor'}, {'type': 'Naming Rules', 'rule': 'Class Naming Conventions', 'abbrev': 'PMD_CNC', 'severity': 'Minor'}, {'type': 'Naming Rules', 'rule': 'Generics Naming', 'abbrev': 'PMD_GN', 'severity': 'Minor'}, {'type': 'Naming Rules', 'rule': 'Method Naming Conventions', 'abbrev': 'PMD_MeNC', 'severity': 'Minor'}, {'type': 'Naming Rules', 'rule': 'Method With Same Name As Enclosing Class', 'abbrev': 'PMD_MWSNAEC', 'severity': 'Minor'}, {'type': 'Naming Rules', 'rule': 'No Package', 'abbrev': 'PMD_NP', 'severity': 'Minor'}, {'type': 'Naming Rules', 'rule': 'Package Case', 'abbrev': 'PMD_PC', 'severity': 'Minor'}, {'type': 'Naming Rules', 'rule': 'Short Class Name', 'abbrev': 'PMD_SCN', 'severity': 'Minor'}, {'type': 'Naming Rules', 'rule': 'Short Method Name', 'abbrev': 'PMD_SMN', 'severity': 'Minor'}, {'type': 'Naming Rules', 'rule': 'Suspicious Constant Field Name', 'abbrev': 'PMD_SCFN', 'severity': 'Minor'}, {'type': 'Naming Rules', 'rule': 'Suspicious Equals Method Name', 'abbrev': 'PMD_SEMN', 'severity': 'Critical'}, {'type': 'Naming Rules', 'rule': 'Suspicious Hashcode Method Name', 'abbrev': 'PMD_SHMN', 'severity': 'Critical'}, {'type': 'Naming Rules', 'rule': 'Variable Naming Conventions', 'abbrev': 'PMD_VNC', 'severity': 'Minor'}, {'type': 'Optimization Rules', 'rule': 'Add Empty String', 'abbrev': 'PMD_AES', 'severity': 'Minor'}, {'type': 'Optimization Rules', 'rule': 'Avoid Array Loops', 'abbrev': 'PMD_AAL', 'severity': 'Major'}, {'type': 'Optimization Rules', 'rule': 'Redundant Field Initializer', 'abbrev': 'PMD_RFI', 'severity': 'Minor'}, {'type': 'Optimization Rules', 'rule': 'Unnecessary Wrapper Object Creation', 'abbrev': 'PMD_UWOC', 'severity': 'Major'}, {'type': 'Optimization Rules', 'rule': 'Use Array List Instead Of Vector', 'abbrev': 'PMD_UALIOV', 'severity': 'Minor'}, {'type': 'Optimization Rules', 'rule': 'Use Arrays As List', 'abbrev': 'PMD_UAAL', 'severity': 'Major'}, {'type': 'Optimization Rules', 'rule': 'Use String Buffer For String Appends', 'abbrev': 'PMD_USBFSA', 'severity': 'Major'}, {'type': 'Security Code Guideline Rules', 'rule': 'Array Is Stored Directly', 'abbrev': 'PMD_AISD', 'severity': 'Major'}, {'type': 'Security Code Guideline Rules', 'rule': 'Method Returns Internal Array', 'abbrev': 'PMD_MRIA', 'severity': 'Major'}, {'type': 'Strict Exception Rules', 'rule': 'Avoid Catching Generic Exception', 'abbrev': 'PMD_ACGE', 'severity': 'Major'}, {'type': 'Strict Exception Rules', 'rule': 'Avoid Catching NPE', 'abbrev': 'PMD_ACNPE', 'severity': 'Critical'}, {'type': 'Strict Exception Rules', 'rule': 'Avoid Catching Throwable', 'abbrev': 'PMD_ACT', 'severity': 'Major'}, {'type': 'Strict Exception Rules', 'rule': 'Avoid Losing Exception Information', 'abbrev': 'PMD_ALEI', 'severity': 'Major'}, {'type': 'Strict Exception Rules', 'rule': 'Avoid Rethrowing Exception', 'abbrev': 'PMD_ARE', 'severity': 'Minor'}, {'type': 'Strict Exception Rules', 'rule': 'Avoid Throwing New Instance Of Same Exception', 'abbrev': 'PMD_ATNIOSE', 'severity': 'Minor'}, {'type': 'Strict Exception Rules', 'rule': 'Avoid Throwing Null Pointer Exception', 'abbrev': 'PMD_ATNPE', 'severity': 'Critical'}, {'type': 'Strict Exception Rules', 'rule': 'Avoid Throwing Raw Exception Types', 'abbrev': 'PMD_ATRET', 'severity': 'Major'}, {'type': 'Strict Exception Rules', 'rule': 'Do Not Extend Java Lang Error', 'abbrev': 'PMD_DNEJLE', 'severity': 'Critical'}, {'type': 'Strict Exception Rules', 'rule': 'Do Not Throw Exception In Finally', 'abbrev': 'PMD_DNTEIF', 'severity': 'Critical'}, {'type': 'Strict Exception Rules', 'rule': 'Exception As Flow Control', 'abbrev': 'PMD_EAFC', 'severity': 'Major'}, {'type': 'String and StringBuffer Rules', 'rule': 'Avoid Duplicate Literals', 'abbrev': 'PMD_ADL', 'severity': 'Major'}, {'type': 'String and StringBuffer Rules', 'rule': 'Avoid String Buffer Field', 'abbrev': 'PMD_ASBF', 'severity': 'Minor'}, {'type': 'String and StringBuffer Rules', 'rule': 'Consecutive Appends Should Reuse', 'abbrev': 'PMD_CASR', 'severity': 'Minor'}, {'type': 'String and StringBuffer Rules', 'rule': 'Consecutive Literal Appends', 'abbrev': 'PMD_CLA', 'severity': 'Minor'}, {'type': 'String and StringBuffer Rules', 'rule': 'Inefficient String Buffering', 'abbrev': 'PMD_ISB', 'severity': 'Minor'}, {'type': 'String and StringBuffer Rules', 'rule': 'String Buffer Instantiation With Char', 'abbrev': 'PMD_SBIWC', 'severity': 'Critical'}, {'type': 'String and StringBuffer Rules', 'rule': 'String Instantiation', 'abbrev': 'PMD_StI', 'severity': 'Minor'}, {'type': 'String and StringBuffer Rules', 'rule': 'String To String', 'abbrev': 'PMD_STS', 'severity': 'Minor'}, {'type': 'String and StringBuffer Rules', 'rule': 'Unnecessary Case Change', 'abbrev': 'PMD_UCC', 'severity': 'Minor'}, {'type': 'String and StringBuffer Rules', 'rule': 'Use Equals To Compare Strings', 'abbrev': 'PMD_UETCS', 'severity': 'Critical'}, {'type': 'Type Resolution Rules', 'rule': 'Clone Method Must Implement Cloneable', 'abbrev': 'PMD_ClMMIC', 'severity': 'Major'}, {'type': 'Type Resolution Rules', 'rule': 'Loose Coupling', 'abbrev': 'PMD_LoC', 'severity': 'Major'}, {'type': 'Type Resolution Rules', 'rule': 'Signature Declare Throws Exception', 'abbrev': 'PMD_SiDTE', 'severity': 'Major'}, {'type': 'Type Resolution Rules', 'rule': 'Unused Imports', 'abbrev': 'PMD_UnI', 'severity': 'Minor'}, {'type': 'Unnecessary and Unused Code Rules', 'rule': 'Unused Local Variable', 'abbrev': 'PMD_ULV', 'severity': 'Major'}, {'type': 'Unnecessary and Unused Code Rules', 'rule': 'Unused Private Field', 'abbrev': 'PMD_UPF', 'severity': 'Major'}, {'type': 'Unnecessary and Unused Code Rules', 'rule': 'Unused Private Method', 'abbrev': 'PMD_UPM', 'severity': 'Major'}]


class SmartSharkConnector():
    """Connector for enabling smartshark features for fine-grained just-in-time data mining."""

    def __init__(self, project_name, project_path, log, regex_only, jira_key, label_name, db_host, db_port, db_name, db_user, db_pw, db_auth):
        connection = {'host': db_host,
                      'port': int(db_port),
                      'db': db_name,
                      'username': db_user,
                      'password': db_pw,
                      'authentication_source': db_auth,
                      'connect': False}
        connect(**connection)

        p = Project.objects.get(name=project_name)
        self.vcs = VCSSystem.objects.get(project_id=p.id)
        self.project_path = project_path
        self._log = log
        self._label_name = label_name
        self._regex_only = regex_only
        self._jira_key = jira_key
        self.cache = {}

    def get_labels_regex(self):
        """1. get project key
           2. filter commits for messages containing project key
           3. filter commits for project keys that link to bugs
           4. find inducing for each file in bug-fixing commit
        """

        its = IssueSystem.objects.get(project_id=self.vcs.project_id)

        # 1. project key is the majority key, we just count for the curren issue system id
        ids = {}
        for i in Issue.objects.filter(issue_system_id=its.id).only('external_id'):
            project_key = i.external_id.split('-')[0]
            if project_key not in ids:
                ids[project_key] = 0
            ids[project_key] += 0
        project_key = max(ids, key=ids.get)

        gr_fix = GitRepository(self.project_path)
        gr_ind = GitRepository(self.project_path)

        needle = r'{}-[0-9]+'.format(project_key)

        inducings = {}
        for c in Commit.objects.filter(vcs_system_id=self.vcs.id).only('id', 'revision_hash', 'message', 'committer_date'):

            # find a matching project-key
            for match in re.finditer(needle, c.message):
                external_id = match.group(0)

                # find a matching issue
                try:
                    i = Issue.objects.get(external_id=external_id, issue_system_id=its.id)
                except Issue.DoesNotExist:
                    continue

                # only fixed and bug issues
                if i.issue_type and i.issue_type.lower() == 'bug' and jira_is_resolved_and_fixed(i):
                    try:
                        commit = gr_fix.get_commit(c.revision_hash)
                    except ValueError:
                        continue

                    # get bug fix modifications but only java files
                    for mod in commit.modifications:
                        # we can not blame added files
                        if mod.change_type == ModificationType.ADD:
                            continue

                        path = mod.new_path
                        if mod.change_type == ModificationType.DELETE:
                            path = mod.old_path

                        if not java_filename_filter(path, production_only=False):
                            continue

                        # collect changed lines for each file changed in bug-fixing commit
                        p = mod.diff_parsed
                        deleted = []
                        for dl in p['deleted']:
                            if not gr_ind._useless_line(dl[1].strip()):
                                deleted.append(dl[0])

                        # blame this file with newest commit=parent commit (otherwise we would trivially get this current commit) for the file
                        # then only find matching lines
                        for bi in gr_ind.repo.blame_incremental('{}^'.format(commit.hash), mod.old_path, w=True):
                            # check suspect boundary date here
                            bug_inducing = Commit.objects.only('committer_date', 'vcs_system_id', 'revision_hash').get(vcs_system_id=self.vcs.id, revision_hash=str(bi.commit))
                            if bug_inducing.committer_date > i.created_at:
                                # suspect
                                continue

                            for d in deleted:
                                if d in bi.linenos:
                                    k = '{}__{}'.format(bi.commit, bi.orig_path)
                                    if k not in inducings.keys():
                                        inducings[k] = []
                                    inducings[k].append('{}__{}__{}'.format(external_id, c.revision_hash, c.committer_date))
        return inducings

    def get_labels(self):
        if self._regex_only:
            return self.get_labels_regex()
        else:
            return self.get_labels_validated()

    def get_labels_validated(self):
        labels = {}
        for inducing_commit in Commit.objects.filter(vcs_system_id=self.vcs.id).only('id', 'revision_hash'):
            for fa in FileAction.objects.filter(commit_id=inducing_commit.id):
                f = File.objects.get(id=fa.file_id)
                if not java_filename_filter(f.path, production_only=False):
                    continue

                for ind in fa.induces:
                    if ind['label'] == self._label_name and ind['szz_type'] != 'hard_suspect':

                        bugfixing_fa = FileAction.objects.get(id=ind['change_file_action_id'])
                        bugfixing_commit = Commit.objects.get(id=bugfixing_fa.commit_id)

                        for issue_id in bugfixing_commit.fixed_issue_ids:
                            try:
                                i = Issue.objects.get(id=issue_id)
                            except Issue.DoesNotExist:
                                continue
                            if jira_is_resolved_and_fixed(i):
                                k = '{}__{}'.format(inducing_commit.revision_hash, f.path)
                                if k not in labels.keys():
                                    labels[k] = []
                                labels[k].append('{}__{}__{}'.format(i.external_id, bugfixing_commit.revision_hash, bugfixing_commit.committer_date))
        return labels

    def get_subfile_metrics_file(self, commit, ces):
        subfile_metrics = {}

        for ces_subfile in CodeEntityState.objects.filter(id__in=commit.code_entity_states, ce_type__in=['method', 'class', 'interface', 'enum'], file_id=ces.file_id):
            for metric, value in ces_subfile.metrics.items():
                if metric not in subfile_metrics.keys():
                    subfile_metrics[metric] = []
                subfile_metrics[metric].append(value)
        subfile_sums = {k: sum(v) for k, v in subfile_metrics.items()}
        return subfile_sums

    def _get_subfile_metrics(self, commit, file_ids):
        ret = {}
        for ces_current_subfile in CodeEntityState.objects.filter(id__in=commit.code_entity_states, ce_type__in=['method', 'class'], file_id__in=file_ids):
            k = str(ces_current_subfile.file_id)
            if k not in ret.keys():
                ret[k] = {}
            for metric, value in ces_current_subfile.metrics.items():
                if metric not in ret[k].keys():
                    ret[k][metric] = []
                ret[k][metric].append(value)

        for file_id, metrics in ret.items():
            for metric_name, values in metrics.items():
                ret[file_id][metric_name] = sum(values)
        return ret

    def _get_file_metrics(self, commit, file_ids):
        ret = {}

        for ces_current in CodeEntityState.objects.filter(id__in=commit.code_entity_states, ce_type='file', file_id__in=file_ids):
            k = str(ces_current.file_id)
            if k not in ret.keys():
                ret[k] = {}

            for metric, value in ces_current.metrics.items():
                if metric not in ret[k].keys():
                    ret[k][metric] = []
                ret[k][metric].append(value)

            for warning in ces_current.linter:
                if warning['l_ty'] not in ret[k].keys():
                    ret[k][warning['l_ty']] = []
                ret[k][warning['l_ty']].append(1)

        for file_id, metrics in ret.items():
            for metric_name, values in metrics.items():
                ret[file_id][metric_name] = sum(values)
        return ret

    def pre_cache(self, needed_commits):
        """Pre-Cache required information"""
        self._log.debug('starting caching')
        already_cached = set()
        for c in Commit.objects.filter(vcs_system_id=self.vcs.id).only('id', 'revision_hash', 'parents').timeout(False):
            if c.revision_hash not in needed_commits:
                continue

            self.cache[c.revision_hash] = get_warning_density(Commit.objects.get(id=c.id))
            already_cached.add(c.revision_hash)

            p = None
            if c.parents:
                p = c.parents[0]

            k = '{}_{}'.format(c.revision_hash, p)
            if k not in self.cache.keys():
                self.cache[k] = self.cache_static_features(c, p)
            self._log.debug('[{}/{}] commits in metrics cache'.format(len(already_cached), len(needed_commits)))
        self._log.debug('finished caching')

    def cache_static_features(self, commit, parent_revision_hash):
        file_ids = set()
        for fa in FileAction.objects.filter(commit_id=commit.id, parent_revision_hash=parent_revision_hash):
            if fa.old_file_id:
                file_ids.add(fa.old_file_id)
            file_ids.add(fa.file_id)

        parent_ces = None
        parent = None
        if parent_revision_hash:
            try:
                parent = Commit.objects.get(revision_hash=parent_revision_hash, vcs_system_id=self.vcs.id)
                parent_ces = CodeEntityState.objects.filter(id__in=parent.code_entity_states, file_id__in=file_ids, ce_type='file')
            except CodeEntityState.DoesNotExist:  # we allow added files which are not present in parent
                pass

        current_ces = None
        try:
            commit = Commit.objects.get(id=commit.id)
            current_ces = CodeEntityState.objects.filter(id__in=commit.code_entity_states, file_id__in=file_ids, ce_type='file')
        except CodeEntityState.DoesNotExist:  # file could have been deleted
            pass

        parent_file_metrics = {}
        parent_subfile_metrics = {}
        if parent_ces:
            parent_subfile_metrics = self._get_subfile_metrics(parent, file_ids)
            parent_file_metrics = self._get_file_metrics(parent, file_ids)

        current_file_metrics = {}
        current_subfile_metrics = {}
        if current_ces:
            current_subfile_metrics = self._get_subfile_metrics(commit, file_ids)
            current_file_metrics = self._get_file_metrics(commit, file_ids)

        ret = {}
        for file_id in file_ids:
            k = str(file_id)
            fname = File.objects.get(id=file_id).path

            # set defaults
            ret[fname] = {'lt': 0, 'current_WD': 0, 'parent_WD': 0, 'delta_WD': 0}
            for m in STATIC:
                ret[fname]['parent_' + m] = 0
                ret[fname]['current_' + m] = 0
                ret[fname]['delta_' + m] = 0
            for m in PMD_RULES:
                ret[fname]['parent_' + m['abbrev']] = 0
                ret[fname]['current_' + m['abbrev']] = 0
                ret[fname]['delta_' + m['abbrev']] = 0

            if k in parent_subfile_metrics.keys():
                for m in STATIC:
                    if m in parent_subfile_metrics[k].keys():
                        ret[fname]['parent_' + m] = parent_subfile_metrics[k][m]

            if k in parent_file_metrics.keys():
                for m in STATIC:
                    if m in parent_file_metrics[k].keys():
                        ret[fname]['parent_' + m] = parent_file_metrics[k][m]

                warning_sum = 0
                for m in PMD_RULES:
                    if m['abbrev'] in parent_file_metrics[k].keys():
                        ret[fname]['parent_' + m['abbrev']] = parent_file_metrics[k][m['abbrev']]
                        warning_sum += parent_file_metrics[k][m['abbrev']]

                if 'LOC' in parent_file_metrics[k].keys():
                    ret[fname]['lt'] = parent_file_metrics[k]['LOC']
                if 'LLOC' in parent_file_metrics[k].keys() and parent_file_metrics[k]['LLOC'] > 0:
                    ret[fname]['parent_WD'] = warning_sum / parent_file_metrics[k]['LLOC']

            if k in current_subfile_metrics.keys():
                for m in STATIC:
                    if m in current_subfile_metrics[k].keys():
                        ret[fname]['current_' + m] = current_subfile_metrics[k][m]

            if k in current_file_metrics.keys():
                for m in STATIC:
                    if m in current_file_metrics[k].keys():
                        ret[fname]['current_' + m] = current_file_metrics[k][m]

                warning_sum = 0
                for m in PMD_RULES:
                    if m['abbrev'] in current_file_metrics[k].keys():
                        ret[fname]['current_' + m['abbrev']] = current_file_metrics[k][m['abbrev']]
                        warning_sum += current_file_metrics[k][m['abbrev']]

                if 'LLOC' in current_file_metrics[k].keys() and current_file_metrics[k]['LLOC'] > 0:
                    ret[fname]['current_WD'] = warning_sum / current_file_metrics[k]['LLOC']

            # deltas
            for m in STATIC:
                ret[fname]['delta_' + m] = ret[fname]['current_' + m] - ret[fname]['parent_' + m]
            for m in PMD_RULES:
                ret[fname]['delta_' + m['abbrev']] = ret[fname]['current_' + m['abbrev']] - ret[fname]['parent_' + m['abbrev']]

            ret[fname]['delta_WD'] = ret[fname]['current_WD'] - ret[fname]['parent_WD']
        return ret

    def get_warning_density(self, revision_hash):
        return self.cache.get(revision_hash, 0)

    def get_warning_density_live(self, revision_hash):
        try:
            c = Commit.objects.get(vcs_system_id=self.vcs.id, revision_hash=revision_hash)
            wd = get_warning_density(c)
        except Commit.DoesNotExist:
            wd = 0
        return wd

    def get_static_features(self, file, commit, parent):
        ret = {}

        # defaults for everything
        ret['lt'] = 0
        for m in STATIC:
            ret['parent_' + m] = 0
            ret['current_' + m] = 0
            ret['delta_' + m] = 0

        # warning metrics
        for m in PMD_RULES:
            ret['parent_' + m['abbrev']] = 0
            ret['current_' + m['abbrev']] = 0
            ret['delta_' + m['abbrev']] = 0

        ret['current_WD'] = 0
        ret['parent_WD'] = 0
        ret['delta_WD'] = 0

        k = '{}_{}'.format(commit, parent)
        tmp = self.cache.get(k, None)
        if not tmp:
            return ret

        ret = self.cache[k].get(file, ret)
        if file in self.cache[k].keys():
            del self.cache[k][file]  # release the memory!
        return ret

    def get_static_features_live(self, file, commit, parent):
        ret = {}

        # defaults for everything
        ret['lt'] = 0
        for m in STATIC:
            ret['parent_' + m] = 0
            ret['current_' + m] = 0
            ret['delta_' + m] = 0

        # warning metrics
        for m in PMD_RULES:
            ret['parent_' + m['abbrev']] = 0
            ret['current_' + m['abbrev']] = 0
            ret['delta_' + m['abbrev']] = 0

        ret['current_WD'] = 0
        ret['parent_WD'] = 0
        ret['delta_WD'] = 0

        try:
            commit = Commit.objects.get(vcs_system_id=self.vcs.id, revision_hash=commit)
        except Commit.DoesNotExist:
            return ret

        parent_ces = None
        if commit.parents:
            try:
                parent = Commit.objects.get(revision_hash=parent, vcs_system_id=self.vcs.id)
                parent_ces = CodeEntityState.objects.get(id__in=parent.code_entity_states, long_name=file, ce_type='file')
                ret['lt'] += parent_ces.metrics['LOC']
            except CodeEntityState.DoesNotExist:  # we allow added files which are not present in parent
                pass

        current_ces = None
        try:
            current_ces = CodeEntityState.objects.get(id__in=commit.code_entity_states, long_name=file, ce_type='file')
        except CodeEntityState.DoesNotExist:  # file could have been deleted
            pass

        if parent_ces:
            parent_subfile_metrics = self._get_subfile_metrics(parent, parent_ces)

            for m in STATIC:
                if m in parent_ces.metrics.keys():
                    ret['parent_' + m] = parent_ces.metrics[m]
                elif m in parent_subfile_metrics.keys():
                    ret['parent_' + m] = parent_subfile_metrics[m]

            # get warning density
            wl = get_warning_list([parent_ces.id])
            if ret['parent_LLOC'] > 0 and wl:
                ret['parent_WD'] = sum(w['sum'] for w in wl) / ret['parent_LLOC']

        if current_ces:
            current_subfile_metrics = self._get_subfile_metrics(commit, current_ces)

            for m in STATIC:
                if m in current_ces.metrics.keys():
                    ret['current_' + m] = current_ces.metrics[m]
                elif m in current_subfile_metrics.keys():
                    ret['current_' + m] = current_subfile_metrics[m]

            # get warning density
            wl = get_warning_list([current_ces.id])
            if ret['current_LLOC'] > 0 and wl:
                ret['current_WD'] = sum(w['sum'] for w in wl) / ret['current_LLOC']

        for m in STATIC:
            ret['delta_' + m] = ret['current_' + m] - ret['parent_' + m]

        if parent_ces:
            for w in parent_ces.linter:
                ret['parent_' + w['l_ty']] += 1
        if current_ces:
            for w in current_ces.linter:
                ret['current_' + w['l_ty']] += 1

        for m in PMD_RULES:
            ret['delta_' + m['abbrev']] = ret['current_' + m['abbrev']] - ret['parent_' + m['abbrev']]

        ret['delta_WD'] = ret['current_WD'] - ret['parent_WD']
        return ret
