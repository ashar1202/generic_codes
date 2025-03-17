import os
import json
import re
import requests
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from datetime import datetime
from openai import OpenAI

@dataclass
class PRGenerationReadiness:
    """Data class to store PR generation readiness analysis results"""
    ticket_id: str
    title: str
    is_ready: bool
    overall_score: float
    criteria_scores: Dict[str, float]
    gaps: List[str]
    recommendations: List[str]
    analysis: str
    timestamp: str = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class JiraTicketAnalyzer:
    """Class to analyze Jira tickets for AI-driven PR generation readiness"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o"):
        """Initialize the analyzer with API key and model"""
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("No API key provided. Set the OPENAI_API_KEY environment variable or pass it as an argument.")
        
        self.model = model
        self.client = OpenAI(api_key=self.api_key)
        self.system_prompt = """You are an expert software engineering consultant specializing in evaluating 
requirements for AI-driven PR generation. You understand both complex software development tasks and 
simple technical maintenance operations."""
    
    def is_simple_technical_task(self, ticket_content: str) -> bool:
        """
        Determine if a ticket is a simple technical task like a version upgrade
        that AI tools can generally handle well despite minimal description.
        """
        # Look for common patterns in simple technical tasks
        simple_patterns = [
            r'upgrade|update|bump|increment\s+(\w+)\s+(to|version)\s+([\d\.]+)',
            r'dependency\s+upgrade',
            r'version\s+bump',
            r'patch\s+(\w+)',
            r'security\s+fix',
            r'bump\s+version',
            r'update\s+library',
        ]
        
        # Check if the ticket is short (likely a one-liner)
        is_short = len(ticket_content.strip().split('\n')) < 5
        
        # Check if it matches any simple patterns
        matches_pattern = any(re.search(pattern, ticket_content.lower()) for pattern in simple_patterns)
        
        return is_short and matches_pattern
    
    def analyze_with_previous_results(self, 
                                     ticket_content: str, 
                                     previous_analysis: Optional[Dict[str, Any]] = None) -> PRGenerationReadiness:
        """
        Analyze a Jira ticket taking into account previous analysis results if available
        
        Args:
            ticket_content: The content of the Jira ticket
            previous_analysis: Optional previous analysis results from another tool
            
        Returns:
            PRGenerationReadiness object with analysis results
        """
        # Check if this is a simple technical task first
        if self.is_simple_technical_task(ticket_content):
            # For simple technical tasks, we can give a high score with minimal analysis
            ticket_id = re.search(r'([A-Z]+-\d+)', ticket_content)
            ticket_id = ticket_id.group(1) if ticket_id else "Unknown"
            
            title_match = re.search(r'Title:\s*(.+)(?:\n|$)', ticket_content)
            title = title_match.group(1).strip() if title_match else "Simple Technical Task"
            
            return PRGenerationReadiness(
                ticket_id=ticket_id,
                title=title,
                is_ready=True,
                overall_score=8.5,  # High confidence but not perfect
                criteria_scores={
                    "problem_clarity": 9.0,
                    "technical_specificity": 8.0,
                    "codebase_context": 8.0,
                    "acceptance_criteria": 8.0,
                    "edge_cases": 7.0
                },
                gaps=[],
                recommendations=["Though minimal, this simple technical task has sufficient context for AI-driven PR generation"],
                analysis="This appears to be a simple technical task like a version upgrade or dependency update. These tasks typically have well-defined patterns that AI tools like Devin can handle with minimal description."
            )
        
        # Create the prompt for GPT-4o, incorporating previous analysis if available
        prompt = self._create_analysis_prompt(ticket_content, previous_analysis)
        
        try:
            # Make the API call
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1  # Lower temperature for more consistent analysis
            )
            
            # Parse the response
            result = json.loads(response.choices[0].message.content)
            
            # Extract ticket ID and title
            ticket_id = re.search(r'([A-Z]+-\d+)', ticket_content)
            ticket_id = ticket_id.group(1) if ticket_id else result.get("ticket_id", "Unknown")
            
            title_match = re.search(r'Title:\s*(.+)(?:\n|$)', ticket_content)
            title = title_match.group(1).strip() if title_match else result.get("title", "Unknown")
            
            # Create and return the analysis object
            return PRGenerationReadiness(
                ticket_id=ticket_id,
                title=title,
                is_ready=result.get("is_ready", False),
                overall_score=result.get("overall_score", 0),
                criteria_scores=result.get("criteria_scores", {}),
                gaps=result.get("gaps", []),
                recommendations=result.get("recommendations", []),
                analysis=result.get("analysis", "")
            )
            
        except Exception as e:
            print(f"Error analyzing ticket: {str(e)}")
            raise
            
    def _create_analysis_prompt(self, ticket_content: str, previous_analysis: Optional[Dict[str, Any]] = None) -> str:
        """Create a detailed prompt for the LLM to analyze the ticket"""
        
        # Base prompt
        prompt = f"""
## JIRA TICKET ANALYSIS FOR AI PR GENERATION

### Ticket Content:
```
{ticket_content}
```

"""
        # Add previous analysis if available
        if previous_analysis:
            prompt += f"""
### Previous Analysis Results:
```json
{json.dumps(previous_analysis, indent=2)}
```

Take the above previous analysis into account. It evaluated the ticket for general code generation readiness. 
Your task is to specifically assess if an AI development tool like Devin can generate a complete PR from this ticket.
"""

        # Complete the prompt with evaluation instructions
        prompt += """
### Evaluation Instructions:
Analyze this Jira ticket to determine if it contains enough information for an AI development tool (like Devin) 
to automatically generate a complete Pull Request without requiring additional human input or clarification.

Evaluate based on these specific criteria:
1. Problem clarity (0-10): Is the issue or feature clearly defined for an AI to understand?
2. Technical specificity (0-10): Are implementation details provided that guide where and how code should be changed?
3. Codebase context (0-10): Is there enough information about the codebase structure and relevant files?
4. Acceptance criteria (0-10): Are there clear criteria for a successful implementation that the AI can test against?
5. Edge cases & constraints (0-10): Are limitations, requirements and edge cases described?

Consider that some very simple technical tasks (like version upgrades) may require minimal description
because they follow standard patterns that AI tools can recognize and implement correctly.

### Response Format:
Return your analysis as a JSON object with this structure:
```json
{
    "is_ready": true/false,
    "overall_score": 0-10,
    "criteria_scores": {
        "problem_clarity": 0-10,
        "technical_specificity": 0-10, 
        "codebase_context": 0-10,
        "acceptance_criteria": 0-10,
        "edge_cases": 0-10
    },
    "gaps": ["list of specific missing information"],
    "recommendations": ["list of suggestions to improve the ticket"],
    "analysis": "brief summary explaining the score and readiness assessment"
}
```

Provide only the JSON object in your response, no additional text.
"""
        return prompt

def fetch_jira_ticket(ticket_id: str, jira_url: str, username: str, api_token: str) -> Optional[str]:
    """Fetch a ticket from Jira"""
    auth = (username, api_token)
    endpoint = f"{jira_url}/rest/api/2/issue/{ticket_id}"
    
    try:
        response = requests.get(endpoint, auth=auth)
        response.raise_for_status()
        
        ticket_data = response.json()
        
        # Format ticket data into text
        ticket_content = f"""
        Ticket ID: {ticket_data['key']}
        Title: {ticket_data['fields']['summary']}
        Type: {ticket_data['fields']['issuetype']['name']}
        Status: {ticket_data['fields']['status']['name']}
        
        Description:
        {ticket_data['fields'].get('description', 'No description provided')}
        
        Acceptance Criteria:
        {ticket_data['fields'].get('customfield_10000', 'No acceptance criteria provided')}
        """
        
        return ticket_content
        
    except Exception as e:
        print(f"Error fetching Jira ticket: {str(e)}")
        return None

def main():
    # Example ticket content
    example_tickets = [
        # Simple technical ticket
        """
        Ticket ID: INFRA-456
        Title: Upgrade MongoDB from 4.4 to 5.0
        Type: Task
        Status: To Do
        
        Description:
        Upgrade MongoDB version from 4.4 to 5.0 for performance improvements.
        """,
        
        # Complex feature ticket
        """
        Ticket ID: PROJ-123
        Title: Implement user authentication API endpoint
        Type: Feature
        Status: To Do
        
        Description:
        We need to create a new authentication endpoint for the mobile app.
        The endpoint should accept username/password and return a JWT token.
        The token should expire after 24 hours.
        
        Acceptance Criteria:
        - Endpoint available at /api/v1/auth
        - Accepts POST requests with JSON payload containing username and password
        - Returns 200 OK with JWT token on success
        - Returns 401 Unauthorized for invalid credentials
        - JWT token should include user ID and role
        - Token should expire after 24 hours
        """
    ]
    
    # Example previous analysis result
    example_previous_analysis = {
        "is_sufficient": True,
        "overall_score": 8,
        "criteria_scores": {
            "problem_statement": 9,
            "technical_requirements": 8,
            "acceptance_criteria": 9,
            "dependencies": 7,
            "input_output": 8,
            "edge_cases": 6,
            "constraints": 7,
            "context": 8
        },
        "missing_information": ["Implementation details for token generation"],
        "suggested_questions": ["What JWT library should be used?"],
        "analysis": "The ticket provides clear requirements for an authentication endpoint."
    }
    
    # Initialize the analyzer
    analyzer = JiraTicketAnalyzer()
    
    # Analyze each ticket
    for i, ticket in enumerate(example_tickets):
        print(f"\n\n=== ANALYZING TICKET {i+1} ===\n")
        print(ticket)
        
        # Use previous analysis for the second ticket as an example
        previous = example_previous_analysis if i == 1 else None
        
        try:
            result = analyzer.analyze_with_previous_results(ticket, previous)
            
            # Print results
            print("\n=== RESULTS: PR GENERATION READINESS ===")
            print(f"Ticket ID: {result.ticket_id}")
            print(f"Title: {result.title}")
            print(f"Overall Score: {result.overall_score}/10")
            print(f"Ready for AI PR Generation: {'Yes' if result.is_ready else 'No'}")
            
            print("\nCriteria Scores:")
            for criterion, score in result.criteria_scores.items():
                print(f"- {criterion.replace('_', ' ').title()}: {score}/10")
            
            if result.gaps:
                print("\nGaps in Information:")
                for gap in result.gaps:
                    print(f"- {gap}")
                    
            if result.recommendations:
                print("\nRecommendations:")
                for rec in result.recommendations:
                    print(f"- {rec}")
            
            print(f"\nAnalysis: {result.analysis}")
            
        except Exception as e:
            print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()
