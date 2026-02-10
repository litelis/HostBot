"""System prompts and templates for the AI agent."""


class PromptTemplates:
    """Collection of prompt templates for different agent operations."""
    
    # System prompt for the main agent
    AGENT_SYSTEM_PROMPT = """You are an autonomous OS control agent named {agent_name}. Your purpose is to interpret user commands and execute them on the local computer system.

CORE CAPABILITIES:
- Execute system commands and scripts
- Control mouse and keyboard for desktop automation
- Navigate and interact with web browsers
- Manage files, processes, and applications
- Install, configure, and uninstall software
- Modify system settings and environment variables

OPERATIONAL PRINCIPLES:
1. SAFETY FIRST: Always prioritize system safety and data integrity
2. ASK BEFORE ACTING: When uncertain, ask clarifying questions
3. PLAN BEFORE EXECUTING: Break complex tasks into clear steps
4. VERIFY RESULTS: Confirm actions completed successfully
5. REPORT CLEARLY: Provide concise, informative status updates

CONFIRMATION LEVELS:
- Use "critical" for: system modifications, software installation, file deletion, registry changes
- Use "standard" for: file operations, process management, browser navigation
- Use "info" for: reading files, checking status, listing information

You have access to the following tools:
- system: Execute system commands, file operations, process management
- desktop: Control mouse and keyboard, take screenshots
- browser: Navigate web, interact with pages, extract data
- application: Install, configure, uninstall software

Current safety mode: {safety_mode}
Current user: {user_id}
Session ID: {session_id}

Respond with clear, actionable plans. When in doubt, ask for confirmation."""

    # Template for command analysis and planning
    COMMAND_ANALYSIS_TEMPLATE = """Analyze the following user command and determine the best approach:

USER COMMAND: {command}

CONTEXT:
- Current working directory: {cwd}
- Operating system: {os_info}
- Previous actions: {history}

TASK:
1. Interpret the user's intent
2. Identify any ambiguities or missing information
3. Determine required capabilities
4. Assess risk level (low/medium/high/critical)
5. Suggest confirmation level needed

Respond in JSON format:
{{
    "intent": "clear description of what the user wants",
    "ambiguities": ["list any unclear aspects or missing info"],
    "questions": ["questions to ask user if needed"],
    "capabilities_required": ["system", "desktop", "browser", "application"],
    "risk_level": "low|medium|high|critical",
    "confirmation_level": "none|info|standard|critical|emergency",
    "can_proceed": true|false,
    "reasoning": "explanation of your analysis"
}}"""

    # Template for step-by-step planning
    PLANNING_TEMPLATE = """Create a detailed execution plan for the following task:

TASK: {task}

CONTEXT:
{context}

REQUIREMENTS:
- Break down into clear, executable steps
- Each step should be verifiable
- Include error handling considerations
- Specify required confirmation level for each step

Respond in JSON format:
{{
    "plan_id": "unique identifier",
    "description": "overall plan description",
    "estimated_duration": "estimated time in minutes",
    "steps": [
        {{
            "step_number": 1,
            "description": "what this step does",
            "tool": "system|desktop|browser|application",
            "command": "specific command or action",
            "confirmation_level": "none|info|standard|critical",
            "verification": "how to verify this step succeeded",
            "rollback": "how to undo if needed",
            "dependencies": [0]
        }}
    ],
    "risk_assessment": "overall risk evaluation",
    "rollback_plan": "how to undo the entire operation"
}}"""

    # Template for step execution and evaluation
    STEP_EXECUTION_TEMPLATE = """Execute the following step and evaluate the result:

STEP: {step_description}
TOOL: {tool}
COMMAND: {command}

EXECUTION CONTEXT:
{context}

Execute the step and report the outcome.

Respond in JSON format:
{{
    "success": true|false,
    "executed_command": "the actual command that was run",
    "output": "command output or result",
    "error": "error message if failed",
    "verification_result": "whether verification passed",
    "next_action": "continue|retry|rollback|ask_user",
    "notes": "any observations or concerns"
}}"""

    # Template for ambiguity detection
    AMBIGUITY_DETECTION_TEMPLATE = """Analyze this command for ambiguities and missing information:

COMMAND: {command}

Check for:
1. Unclear objectives or goals
2. Missing parameters (versions, paths, names, etc.)
3. Vague references ("that file", "the program", etc.)
4. Multiple possible interpretations
5. Missing context or prerequisites

Respond in JSON format:
{{
    "is_ambiguous": true|false,
    "ambiguities": [
        {{
            "issue": "description of the ambiguity",
            "severity": "low|medium|high",
            "clarification_needed": "what information is needed"
        }}
    ],
    "suggested_questions": ["specific questions to ask the user"],
    "assumed_interpretation": "your best guess at what they mean",
    "confidence": "high|medium|low"
}}"""

    # Template for self-evaluation after task completion
    SELF_EVALUATION_TEMPLATE = """Evaluate the completed task:

ORIGINAL TASK: {task}
EXECUTION SUMMARY: {summary}

Evaluate:
1. Was the task completed successfully?
2. Were there any unexpected issues?
3. Could the execution be improved?
4. Are there any follow-up actions needed?

Respond in JSON format:
{{
    "success": true|false,
    "completion_percentage": 0-100,
    "issues_encountered": ["list of problems"],
    "improvements_suggested": ["how to do better next time"],
    "follow_up_needed": true|false,
    "follow_up_actions": ["what needs to be done next"],
    "user_should_know": ["important information for the user"]
}}"""

    # Template for error analysis and recovery
    ERROR_RECOVERY_TEMPLATE = """An error occurred during execution. Analyze and suggest recovery:

ERROR: {error}
STEP: {step_description}
CONTEXT: {context}

Analyze:
1. What caused the error?
2. Is it recoverable?
3. What are the recovery options?
4. Should we retry, rollback, or ask the user?

Respond in JSON format:
{{
    "error_type": "syntax|permission|not_found|timeout|system|unknown",
    "is_recoverable": true|false,
    "cause_analysis": "what likely caused this",
    "recovery_options": [
        {{
            "action": "retry|rollback|skip|ask_user|abort",
            "description": "what this option does",
            "likelihood_of_success": "high|medium|low"
        }}
    ],
    "recommended_action": "which option to choose",
    "reasoning": "why this is the best approach"
}}"""

    # Template for user communication
    USER_COMMUNICATION_TEMPLATE = """Generate a clear status message for the user:

STATUS: {status}
PROGRESS: {progress}
DETAILS: {details}

TONE: {tone}

Generate a concise, informative message that keeps the user informed without overwhelming them."""

    @classmethod
    def format_system_prompt(cls, **kwargs) -> str:
        """Format the system prompt with variables."""
        return cls.AGENT_SYSTEM_PROMPT.format(**kwargs)
    
    @classmethod
    def format_command_analysis(cls, **kwargs) -> str:
        """Format command analysis template."""
        return cls.COMMAND_ANALYSIS_TEMPLATE.format(**kwargs)
    
    @classmethod
    def format_planning(cls, **kwargs) -> str:
        """Format planning template."""
        return cls.PLANNING_TEMPLATE.format(**kwargs)
    
    @classmethod
    def format_step_execution(cls, **kwargs) -> str:
        """Format step execution template."""
        return cls.STEP_EXECUTION_TEMPLATE.format(**kwargs)
    
    @classmethod
    def format_ambiguity_detection(cls, **kwargs) -> str:
        """Format ambiguity detection template."""
        return cls.AMBIGUITY_DETECTION_TEMPLATE.format(**kwargs)
    
    @classmethod
    def format_self_evaluation(cls, **kwargs) -> str:
        """Format self-evaluation template."""
        return cls.SELF_EVALUATION_TEMPLATE.format(**kwargs)
    
    @classmethod
    def format_error_recovery(cls, **kwargs) -> str:
        """Format error recovery template."""
        return cls.ERROR_RECOVERY_TEMPLATE.format(**kwargs)
    
    @classmethod
    def format_user_communication(cls, **kwargs) -> str:
        """Format user communication template."""
        return cls.USER_COMMUNICATION_TEMPLATE.format(**kwargs)
