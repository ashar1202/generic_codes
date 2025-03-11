"""
Jira Quality Validator for Code Generation Tasks

This system evaluates Jira tickets for code generation tasks and provides quality scores
based on various metrics that are important for AI-powered code generation tools
(similar to how Devin or other AI coding assistants would interpret tickets).
"""

class JiraQualityValidator:
    def __init__(self):
        # Define weights for each metric category
        self.weights = {
            'clarity': 0.25,
            'completeness': 0.25,
            'context': 0.20,
            'constraints': 0.15,
            'testability': 0.15
        }
        
        # Threshold levels for quality scores
        self.quality_levels = {
            'excellent': 0.85,
            'good': 0.70,
            'average': 0.50,
            'poor': 0.30
        }

    def analyze_jira_issue(self, jira_issue):
        """
        Analyzes a Jira issue and returns quality metrics
        
        Args:
            jira_issue (dict): The Jira issue object with required fields
            
        Returns:
            dict: Quality metrics and overall score
        """
        # Extract relevant fields from the Jira issue
        summary = jira_issue.get('summary', '')
        description = jira_issue.get('description', '')
        acceptance_criteria = jira_issue.get('acceptanceCriteria', '')
        components = jira_issue.get('components', [])
        labels = jira_issue.get('labels', [])
        attachments = jira_issue.get('attachments', [])
        comments = jira_issue.get('comments', [])
        
        # Calculate individual metric scores
        clarity_score = self.evaluate_clarity(summary, description)
        completeness_score = self.evaluate_completeness(description, acceptance_criteria)
        context_score = self.evaluate_context(description, components, labels, attachments)
        constraints_score = self.evaluate_constraints(description, comments)
        testability_score = self.evaluate_testability(description, acceptance_criteria)
        
        # Calculate weighted score
        overall_score = (
            self.weights['clarity'] * clarity_score +
            self.weights['completeness'] * completeness_score +
            self.weights['context'] * context_score +
            self.weights['constraints'] * constraints_score +
            self.weights['testability'] * testability_score
        )
        
        # Determine quality level
        if overall_score >= self.quality_levels['excellent']:
            quality_level = "Excellent"
        elif overall_score >= self.quality_levels['good']:
            quality_level = "Good"
        elif overall_score >= self.quality_levels['average']:
            quality_level = "Average"
        elif overall_score >= self.quality_levels['poor']:
            quality_level = "Poor"
        else:
            quality_level = "Inadequate"
        
        # Generate suggestions for improvement
        suggestions = self.generate_suggestions({
            'clarity': clarity_score,
            'completeness': completeness_score,
            'context': context_score,
            'constraints': constraints_score,
            'testability': testability_score
        })
        
        # Return comprehensive analysis
        return {
            'overall_score': round(overall_score, 2),
            'quality_level': quality_level,
            'metrics': {
                'clarity': round(clarity_score, 2),
                'completeness': round(completeness_score, 2),
                'context': round(context_score, 2),
                'constraints': round(constraints_score, 2),
                'testability': round(testability_score, 2)
            },
            'suggestions': suggestions,
            'ai_code_generation_readiness': self.evaluate_ai_readiness(overall_score)
        }
    
    def evaluate_clarity(self, summary, description):
        """
        Evaluates the clarity of the Jira issue
        Measures how clearly the requirements are described
        """
        score = 0.0
        max_score = 1.0
        
        # Check for well-defined title
        if summary and 10 < len(summary) < 100:
            score += 0.2
        
        # Check for description quality
        if description:
            # Check for length - neither too short nor too verbose
            if 100 < len(description) < 2000:
                score += 0.1
            
            # Check for structured content (lists, headings, etc.)
            if any(char in description for char in ['*', '-', '#']):
                score += 0.1
            
            # Check for code examples
            if '{code}' in description or '```' in description:
                score += 0.2
            
            # Check for specific request language
            code_terms = ['function', 'class', 'method', 'implement', 'algorithm', 'API', 'endpoint']
            has_code_terms = any(term.lower() in description.lower() for term in code_terms)
            if has_code_terms:
                score += 0.2
            
            # Check for ambiguous language
            ambiguous_terms = ['etc', 'and so on', 'something like', 'maybe', 'possibly']
            has_ambiguous_terms = any(term.lower() in description.lower() for term in ambiguous_terms)
            if not has_ambiguous_terms:
                score += 0.2
        
        return min(score, max_score)
    
    def evaluate_completeness(self, description, acceptance_criteria):
        """
        Evaluates the completeness of the Jira issue
        Measures whether all necessary information is included
        """
        score = 0.0
        max_score = 1.0
        
        # Check for detailed description
        if description and len(description) > 200:
            score += 0.3
        
        # Check for acceptance criteria
        if acceptance_criteria and len(acceptance_criteria) > 50:
            score += 0.3
            
            # Check for specific, measurable criteria
            if 'should' in acceptance_criteria or 'must' in acceptance_criteria:
                score += 0.2
        
        # Check for input/output descriptions
        if description:
            has_inputs = 'input' in description.lower() or 'parameter' in description.lower()
            has_outputs = 'output' in description.lower() or 'return' in description.lower()
            
            if has_inputs:
                score += 0.1
            if has_outputs:
                score += 0.1
        
        return min(score, max_score)
    
    def evaluate_context(self, description, components, labels, attachments):
        """
        Evaluates the context provided in the Jira issue
        Measures whether there's enough background information
        """
        score = 0.0
        max_score = 1.0
        
        # Check for system context
        if description and any(term in description.lower() for term in ['system', 'component', 'module']):
            score += 0.2
        
        # Check for components specification
        if components and len(components) > 0:
            score += 0.2
        
        # Check for relevant labels
        if labels and len(labels) > 0:
            tech_terms = ['frontend', 'backend', 'api', 'database', 'ui', 'java', 'python', 'javascript', 'react', 'node']
            tech_labels = [label for label in labels if any(tech in label.lower() for tech in tech_terms)]
            
            if tech_labels:
                score += 0.2
        
        # Check for helpful attachments (diagrams, mockups, etc.)
        if attachments and len(attachments) > 0:
            score += 0.2
        
        # Check for dependencies mentioned
        if description and any(term in description.lower() for term in ['depends on', 'related to', 'prerequisite']):
            score += 0.2
        
        return min(score, max_score)
    
    def evaluate_constraints(self, description, comments):
        """
        Evaluates constraints and requirements in the Jira issue
        Measures whether technical constraints are well-defined
        """
        score = 0.0
        max_score = 1.0
        
        # Check for technical constraints
        if description:
            # Performance requirements
            if any(term in description.lower() for term in ['performance', 'latency', 'throughput']):
                score += 0.2
            
            # Security requirements
            if any(term in description.lower() for term in ['security', 'authentication', 'authorization']):
                score += 0.2
            
            # Compatibility requirements
            if any(term in description.lower() for term in ['compatible', 'support for', 'version']):
                score += 0.2
            
            # Resource constraints
            if any(term in description.lower() for term in ['memory', 'cpu', 'storage']):
                score += 0.2
        
        # Check for clarifications in comments
        if comments and len(comments) > 0:
            technical_terms = ['technical', 'implementation', 'constraint']
            technical_comments = [
                comment for comment in comments 
                if any(term in comment.get('body', '').lower() for term in technical_terms)
            ]
            
            if technical_comments:
                score += 0.2
        
        return min(score, max_score)
    
    def evaluate_testability(self, description, acceptance_criteria):
        """
        Evaluates the testability of the requirements
        Measures whether the acceptance criteria are testable
        """
        score = 0.0
        max_score = 1.0
        
        # Check for test cases or examples
        test_terms = ['test case', 'example:', 'sample input', 'sample output']
        if description and any(term in description.lower() for term in test_terms):
            score += 0.3
        
        # Check for measurable acceptance criteria
        if acceptance_criteria:
            # Look for specific, measurable statements
            specific_terms = ['should return', 'must produce', 'will validate']
            has_specific_criteria = any(term in acceptance_criteria for term in specific_terms)
            
            if has_specific_criteria:
                score += 0.3
            
            # Look for edge cases
            edge_terms = ['edge case', 'error handling', 'exception']
            if any(term in acceptance_criteria.lower() for term in edge_terms):
                score += 0.2
        
        # Check for validation methods
        validation_terms = ['validate', 'verify', 'test']
        if description and any(term in description.lower() for term in validation_terms):
            score += 0.2
        
        return min(score, max_score)
    
    def generate_suggestions(self, metrics):
        """
        Generates improvement suggestions based on metric scores
        """
        suggestions = []
        
        if metrics['clarity'] < 0.7:
            suggestions.append("Improve clarity by using more specific language and providing code examples or pseudocode.")
        
        if metrics['completeness'] < 0.7:
            suggestions.append("Add more details about inputs/outputs and define clear acceptance criteria.")
        
        if metrics['context'] < 0.7:
            suggestions.append("Provide more context about where this code fits in the system and any related components.")
        
        if metrics['constraints'] < 0.7:
            suggestions.append("Define technical constraints like performance requirements, security needs, and compatibility.")
        
        if metrics['testability'] < 0.7:
            suggestions.append("Include test cases, examples, and edge cases to improve testability.")
        
        return suggestions
    
    def evaluate_ai_readiness(self, overall_score):
        """
        Evaluates if the ticket is ready for AI code generation
        """
        if overall_score >= self.quality_levels['good']:
            confidence = round((overall_score - self.quality_levels['good']) / (1 - self.quality_levels['good']) * 100)
            return {
                'is_ready': True,
                'confidence': f"{confidence}%",
                'message': "This ticket contains sufficient information for AI code generation."
            }
        else:
            confidence = round((self.quality_levels['good'] - overall_score) / self.quality_levels['good'] * 100)
            return {
                'is_ready': False,
                'confidence': f"{confidence}%",
                'message': "This ticket needs improvement before it's ready for AI code generation."
            }


def validate_jira_example():
    """
    Sample usage of the Jira Quality Validator
    """
    validator = JiraQualityValidator()
    
    # Example Jira issue (good quality)
    good_jira_issue = {
        'summary': "Implement pagination service for product search API",
        'description': """
        # Background
        The product search API currently returns all results at once, which is causing performance issues when there are many products.
        
        # Requirements
        Implement a pagination service that will:
        - Accept page number and page size parameters
        - Return paginated results with total count
        - Handle edge cases (invalid page numbers, empty results)
        
        ## Input Parameters
        - page: number (default: 1)
        - pageSize: number (default: 20, max: 100)
        - searchQuery: string (existing parameter)
        
        ## Output Format
        {
          "results": [...], // Array of product objects
          "pagination": {
            "totalItems": number,
            "totalPages": number,
            "currentPage": number,
            "pageSize": number,
            "hasNextPage": boolean,
            "hasPreviousPage": boolean
          }
        }
        
        # Example
        GET /api/products?search=shoes&page=2&pageSize=10
        
        # Performance Requirements
        - The pagination logic should not significantly increase query time
        - Response time should remain under 200ms for typical queries
        """,
        'acceptanceCriteria': """
        - API accepts page and pageSize parameters
        - API returns correct pagination metadata
        - API handles invalid page numbers by returning the first page
        - API handles pageSize > 100 by capping at 100
        - API returns proper error responses for other error conditions
        - All existing tests for the product search API still pass
        - New tests for pagination functionality are added
        """,
        'components': ["Backend", "API"],
        'labels': ["pagination", "api", "performance", "nodejs"],
        'attachments': [{"name": "pagination_flow.png"}],
        'comments': [
            {
                'body': "Please make sure this is compatible with the filtering system implemented in JIRA-456."
            },
            {
                'body': "Technical note: Consider using the existing QueryBuilder interface for consistency."
            }
        ]
    }
    
    # Example Jira issue (poor quality)
    poor_jira_issue = {
        'summary': "Add pagination",
        'description': "We need pagination for the products page. Please implement something similar to what we have on the users page.",
        'acceptanceCriteria': "Pagination works correctly",
        'components': [],
        'labels': ["frontend"],
        'attachments': [],
        'comments': []
    }
    
    # Analyze both examples
    good_analysis = validator.analyze_jira_issue(good_jira_issue)
    poor_analysis = validator.analyze_jira_issue(poor_jira_issue)
    
    print("=== Good Quality Jira Analysis ===")
    import json
    print(json.dumps(good_analysis, indent=2))
    
    print("\n=== Poor Quality Jira Analysis ===")
    print(json.dumps(poor_analysis, indent=2))
    
    return good_analysis, poor_analysis


if __name__ == "__main__":
    validate_jira_example()