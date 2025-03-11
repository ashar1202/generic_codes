import requests
import json
import os
from typing import Dict, List, Tuple, Any
import argparse
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class JiraTicketValidator:
    """
    A class that validates Jira tickets using LLM-based validation and critique.
    """
    
    def __init__(self, api_key: str = None, model: str = "gpt-4", jira_url: str = None, jira_token: str = None):
        """
        Initialize the validator with API credentials.
        
        Args:
            api_key: The API key for the LLM service
            model: The LLM model to use (default: gpt-4)
            jira_url: The Jira instance URL
            jira_token: The Jira API token
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("API key is required. Set it as an argument or as OPENAI_API_KEY environment variable.")
            
        self.model = model
        self.jira_url = jira_url or os.getenv("JIRA_URL")
        self.jira_token = jira_token or os.getenv("JIRA_TOKEN")
        self.jira_user = os.getenv("JIRA_USER")
        
        # Quality criteria for Jira tickets
        self.ticket_criteria = {
            "title": "Title should be clear, concise, and descriptive",
            "description": "Description should provide context, requirements, and expected outcomes",
            "acceptance_criteria": "Acceptance criteria should be specific, testable, and complete",
            "steps_to_reproduce": "For bugs, steps to reproduce should be detailed and clear",
            "priority": "Priority level should match the issue's impact and urgency",
            "assignee": "Ticket should have an appropriate assignee if ready for work",
            "labels": "Relevant labels should be applied for categorization",
            "attachments": "Screenshots or relevant files should be included when helpful",
            "due_date": "Critical tickets should have reasonable due dates"
        }
        
    def _call_llm_api(self, prompt: str) -> Dict[str, Any]:
        """
        Call the LLM API with the given prompt.
        
        Args:
            prompt: The prompt to send to the LLM
            
        Returns:
            Dictionary containing the LLM response
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 1000
        }
        
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API call failed: {e}")
            raise
    
    def get_jira_ticket(self, ticket_id: str) -> Dict[str, Any]:
        """
        Retrieve a Jira ticket by its ID.
        
        Args:
            ticket_id: The ID of the Jira ticket
            
        Returns:
            Dictionary containing the Jira ticket data
        """
        if not all([self.jira_url, self.jira_token, self.jira_user]):
            raise ValueError("Jira API credentials are required")
            
        url = f"{self.jira_url}/rest/api/2/issue/{ticket_id}"
        
        auth = (self.jira_user, self.jira_token)
        
        try:
            response = requests.get(url, auth=auth)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to retrieve Jira ticket: {e}")
            raise
    
    def format_ticket_for_validation(self, ticket: Dict[str, Any]) -> str:
        """
        Format a Jira ticket for validation.
        
        Args:
            ticket: Dictionary containing the Jira ticket data
            
        Returns:
            Formatted ticket as a string
        """
        formatted = f"Ticket ID: {ticket.get('key', 'Unknown')}\n"
        formatted += f"Title: {ticket.get('fields', {}).get('summary', 'Missing')}\n"
        formatted += f"Type: {ticket.get('fields', {}).get('issuetype', {}).get('name', 'Unknown')}\n"
        formatted += f"Priority: {ticket.get('fields', {}).get('priority', {}).get('name', 'Unknown')}\n"
        formatted += f"Status: {ticket.get('fields', {}).get('status', {}).get('name', 'Unknown')}\n"
        formatted += f"Assignee: {ticket.get('fields', {}).get('assignee', {}).get('displayName', 'Unassigned')}\n"
        formatted += f"Reporter: {ticket.get('fields', {}).get('reporter', {}).get('displayName', 'Unknown')}\n"
        formatted += f"Created: {ticket.get('fields', {}).get('created', 'Unknown')}\n"
        
        # Description
        formatted += "\nDescription:\n"
        formatted += f"{ticket.get('fields', {}).get('description', 'No description provided')}\n"
        
        # Custom fields - acceptance criteria
        for field_name, field_value in ticket.get('fields', {}).items():
            if 'acceptance criteria' in field_name.lower() and field_value:
                formatted += "\nAcceptance Criteria:\n"
                formatted += f"{field_value}\n"
        
        # Labels
        labels = ticket.get('fields', {}).get('labels', [])
        if labels:
            formatted += "\nLabels: " + ", ".join(labels) + "\n"
        
        # Attachments
        attachments = ticket.get('fields', {}).get('attachment', [])
        if attachments:
            formatted += "\nAttachments:\n"
            for attachment in attachments:
                formatted += f"- {attachment.get('filename', 'Unknown file')}\n"
        
        return formatted
    
    def validate_ticket(self, ticket_content: str) -> Dict[str, Any]:
        """
        Validate a Jira ticket using the LLM.
        
        Args:
            ticket_content: Formatted ticket content as a string
            
        Returns:
            Dictionary containing validation results
        """
        criteria_list = "\n".join([f"- {key}: {value}" for key, value in self.ticket_criteria.items()])
        
        prompt = f"""
        You are a Jira ticket quality validator. Evaluate the following ticket for quality and provide specific feedback.
        
        Quality criteria to check:
        {criteria_list}
        
        For each criterion, provide:
        1. A score from 1-5 (where 1 is poor and 5 is excellent)
        2. Specific feedback and suggestions for improvement
        
        Here is the ticket to evaluate:
        
        {ticket_content}
        
        Format your response as a JSON object with the following structure:
        {{
            "overall_score": float,
            "criteria_scores": {{
                "title": {{
                    "score": int,
                    "feedback": "string"
                }},
                // other criteria with same structure
            }},
            "summary": "string with overall assessment",
            "improvement_suggestions": ["string", "string"]
        }}
        
        Provide only the JSON object in your response, with no additional text.
        """
        
        try:
            response = self._call_llm_api(prompt)
            content = response.get('choices', [{}])[0].get('message', {}).get('content', '{}')
            
            # Try to parse the JSON
            try:
                validation_result = json.loads(content)
                return validation_result
            except json.JSONDecodeError:
                logger.error("Failed to parse LLM response as JSON")
                # Try to extract JSON if it's embedded in other text
                import re
                json_match = re.search(r'({.*})', content, re.DOTALL)
                if json_match:
                    try:
                        validation_result = json.loads(json_match.group(1))
                        return validation_result
                    except json.JSONDecodeError:
                        pass
                
                # Return a fallback response
                return {
                    "overall_score": 0,
                    "criteria_scores": {},
                    "summary": "Failed to process validation results",
                    "improvement_suggestions": ["Error in processing. Please try again."]
                }
                
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            raise
    
    def critique_validation(self, ticket_content: str, validation_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Critique the validation results using a second LLM call to ensure quality.
        
        Args:
            ticket_content: Formatted ticket content as a string
            validation_result: Dictionary containing the validation results
            
        Returns:
            Dictionary containing the critique results
        """
        validation_json = json.dumps(validation_result, indent=2)
        
        prompt = f"""
        You are a quality assurance expert for Jira ticket validation. Review the following ticket and its validation results.
        Your job is to critique the validation and ensure it's fair, accurate, and helpful.
        
        Ticket:
        {ticket_content}
        
        Validation Results:
        {validation_json}
        
        Please provide:
        1. Any scores that seem too harsh or too lenient
        2. Any missing feedback or suggestions that would help improve the ticket
        3. Any inaccuracies in the validation
        4. Additional improvement suggestions that were not captured
        
        Format your response as a JSON object with the following structure:
        {{
            "critique_summary": "string with overall assessment of the validation",
            "score_adjustments": {{
                "criteria_name": {{
                    "original_score": int,
                    "suggested_score": int,
                    "reasoning": "string"
                }},
                // any other criteria that need adjustment
            }},
            "additional_suggestions": ["string", "string"],
            "final_verdict": "string with final assessment of ticket quality"
        }}
        
        Provide only the JSON object in your response, with no additional text.
        """
        
        try:
            response = self._call_llm_api(prompt)
            content = response.get('choices', [{}])[0].get('message', {}).get('content', '{}')
            
            # Try to parse the JSON
            try:
                critique_result = json.loads(content)
                return critique_result
            except json.JSONDecodeError:
                logger.error("Failed to parse LLM critique response as JSON")
                # Try to extract JSON if it's embedded in other text
                import re
                json_match = re.search(r'({.*})', content, re.DOTALL)
                if json_match:
                    try:
                        critique_result = json.loads(json_match.group(1))
                        return critique_result
                    except json.JSONDecodeError:
                        pass
                
                # Return a fallback response
                return {
                    "critique_summary": "Failed to process critique results",
                    "score_adjustments": {},
                    "additional_suggestions": ["Error in processing. Please try again."],
                    "final_verdict": "Unable to provide final assessment due to processing error."
                }
                
        except Exception as e:
            logger.error(f"Critique failed: {e}")
            raise
    
    def apply_critique(self, validation_result: Dict[str, Any], critique_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply the critique to the validation results to create a final assessment.
        
        Args:
            validation_result: Dictionary containing the validation results
            critique_result: Dictionary containing the critique results
            
        Returns:
            Dictionary containing the final assessment
        """
        final_result = validation_result.copy()
        
        # Apply score adjustments
        for criteria, adjustment in critique_result.get('score_adjustments', {}).items():
            if criteria in final_result.get('criteria_scores', {}):
                original_score = adjustment.get('original_score')
                suggested_score = adjustment.get('suggested_score')
                
                if original_score and suggested_score:
                    final_result['criteria_scores'][criteria]['score'] = suggested_score
                    final_result['criteria_scores'][criteria]['feedback'] += f" [Adjusted from {original_score} to {suggested_score}: {adjustment.get('reasoning', 'No reasoning provided')}]"
        
        # Add additional suggestions
        additional_suggestions = critique_result.get('additional_suggestions', [])
        if additional_suggestions:
            final_result['improvement_suggestions'].extend(additional_suggestions)
            # Remove duplicates while preserving order
            final_result['improvement_suggestions'] = list(dict.fromkeys(final_result['improvement_suggestions']))
        
        # Update summary with final verdict
        final_verdict = critique_result.get('final_verdict')
        if final_verdict:
            final_result['summary'] += f"\n\nFinal verdict: {final_verdict}"
        
        # Recalculate overall score based on potentially adjusted criteria scores
        if final_result.get('criteria_scores'):
            scores = [score_data.get('score', 0) for score_data in final_result['criteria_scores'].values()]
            if scores:
                final_result['overall_score'] = sum(scores) / len(scores)
        
        # Add critique summary
        critique_summary = critique_result.get('critique_summary')
        if critique_summary:
            final_result['critique_summary'] = critique_summary
            
        return final_result
    
    def validate_jira_issue(self, ticket_id: str = None, ticket_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Main method to validate a Jira issue.
        
        Args:
            ticket_id: The ID of the Jira ticket (optional if ticket_data is provided)
            ticket_data: Dictionary containing the Jira ticket data (optional if ticket_id is provided)
            
        Returns:
            Dictionary containing the final assessment results
        """
        # Get ticket data - either from provided data or by ID
        if ticket_data is None:
            if ticket_id is None:
                raise ValueError("Either ticket_id or ticket_data must be provided")
            ticket_data = self.get_jira_ticket(ticket_id)
        
        # Format the ticket for validation
        formatted_ticket = self.format_ticket_for_validation(ticket_data)
        
        # Validate the ticket
        validation_result = self.validate_ticket(formatted_ticket)
        
        # Critique the validation
        critique_result = self.critique_validation(formatted_ticket, validation_result)
        
        # Apply the critique to create final assessment
        final_assessment = self.apply_critique(validation_result, critique_result)
        
        return final_assessment

def main():
    """
    Main function to run the validator from command line.
    """
    parser = argparse.ArgumentParser(description='Validate Jira ticket quality')
    parser.add_argument('ticket_id', help='Jira ticket ID to validate')
    parser.add_argument('--api-key', help='API key for LLM service')
    parser.add_argument('--model', default='gpt-4', help='LLM model to use')
    parser.add_argument('--jira-url', help='Jira instance URL')
    parser.add_argument('--jira-token', help='Jira API token')
    parser.add_argument('--output', choices=['json', 'text'], default='text', help='Output format')
    
    args = parser.parse_args()
    
    try:
        validator = JiraTicketValidator(
            api_key=args.api_key,
            model=args.model,
            jira_url=args.jira_url,
            jira_token=args.jira_token
        )
        
        result = validator.validate_jira_issue(args.ticket_id)
        
        if args.output == 'json':
            print(json.dumps(result, indent=2))
        else:
            print("\n=== JIRA TICKET QUALITY ASSESSMENT ===\n")
            print(f"Ticket ID: {args.ticket_id}")
            print(f"Overall Score: {result.get('overall_score', 0):.2f}/5.0")
            print("\n--- CRITERIA SCORES ---")
            
            for criteria, data in result.get('criteria_scores', {}).items():
                print(f"{criteria.capitalize()}: {data.get('score', 0)}/5 - {data.get('feedback', 'No feedback')}")
            
            print("\n--- IMPROVEMENT SUGGESTIONS ---")
            for suggestion in result.get('improvement_suggestions', []):
                print(f"- {suggestion}")
            
            print(f"\nSummary: {result.get('summary', 'No summary provided')}")
            
            if 'critique_summary' in result:
                print(f"\nCritique: {result.get('critique_summary')}")
            
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    main()