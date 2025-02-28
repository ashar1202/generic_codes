import requests
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import re
import json
import os
from collections import Counter

class JiraQualityChecker:
    def __init__(self, jira_url, username, api_token):
        """
        Initialize the Jira Quality Checker with connection credentials.
        
        Args:
            jira_url (str): The base URL of your Jira instance (e.g., 'https://your-domain.atlassian.net')
            username (str): Jira account username/email
            api_token (str): Jira API token
        """
        self.jira_url = jira_url.rstrip('/')
        self.auth = (username, api_token)
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
    
    def fetch_issues(self, jql_query, fields=None, max_results=1000):
        """
        Fetch issues from Jira using JQL query.
        
        Args:
            jql_query (str): JQL query string
            fields (list, optional): List of fields to include in the response
            max_results (int, optional): Maximum number of results to return
            
        Returns:
            list: List of Jira issues
        """
        if fields is None:
            fields = ["summary", "description", "issuetype", "status", "assignee", 
                      "reporter", "priority", "created", "updated", "labels", 
                      "components", "fixVersions"]
        
        api_endpoint = f"{self.jira_url}/rest/api/3/search"
        
        start_at = 0
        all_issues = []
        
        while True:
            payload = {
                "jql": jql_query,
                "startAt": start_at,
                "maxResults": min(100, max_results - len(all_issues)),
                "fields": fields
            }
            
            response = requests.post(
                api_endpoint,
                headers=self.headers,
                auth=self.auth,
                json=payload
            )
            
            if response.status_code != 200:
                raise Exception(f"API request failed with status code {response.status_code}: {response.text}")
                
            data = response.json()
            issues = data.get("issues", [])
            all_issues.extend(issues)
            
            if len(issues) == 0 or len(all_issues) >= max_results:
                break
                
            start_at += len(issues)
        
        return all_issues
    
    def check_missing_fields(self, issues, required_fields):
        """
        Check for missing required fields in issues.
        
        Args:
            issues (list): List of Jira issues
            required_fields (list): List of required field names
            
        Returns:
            dict: Dictionary with issues missing required fields
        """
        missing_fields = {}
        
        for issue in issues:
            key = issue["key"]
            fields = issue["fields"]
            missing = []
            
            for field in required_fields:
                if field not in fields or fields[field] is None or fields[field] == "":
                    missing.append(field)
                elif isinstance(fields[field], dict) and "name" in fields[field] and fields[field]["name"] is None:
                    missing.append(field)
                elif isinstance(fields[field], list) and len(fields[field]) == 0:
                    missing.append(field)
                    
            if missing:
                missing_fields[key] = missing
        
        return missing_fields
    
    def check_stale_issues(self, issues, days_threshold=30):
        """
        Identify stale issues that haven't been updated recently.
        
        Args:
            issues (list): List of Jira issues
            days_threshold (int, optional): Number of days to consider an issue stale
            
        Returns:
            list: List of stale issues
        """
        stale_issues = []
        now = datetime.now()
        
        for issue in issues:
            key = issue["key"]
            updated_str = issue["fields"].get("updated")
            
            if updated_str:
                updated_date = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
                days_since_update = (now - updated_date.replace(tzinfo=None)).days
                
                if days_since_update > days_threshold:
                    stale_issues.append({
                        "key": key,
                        "days_since_update": days_since_update,
                        "status": issue["fields"].get("status", {}).get("name")
                    })
        
        return stale_issues
    
    def check_summary_quality(self, issues, min_length=10):
        """
        Check quality of issue summaries.
        
        Args:
            issues (list): List of Jira issues
            min_length (int, optional): Minimum acceptable summary length
            
        Returns:
            dict: Dictionary with issues having poor summaries
        """
        poor_summaries = {}
        
        for issue in issues:
            key = issue["key"]
            summary = issue["fields"].get("summary", "")
            
            if len(summary) < min_length:
                poor_summaries[key] = {
                    "summary": summary,
                    "length": len(summary),
                    "reason": "Too short"
                }
            elif summary.isupper():
                poor_summaries[key] = {
                    "summary": summary,
                    "length": len(summary),
                    "reason": "All uppercase"
                }
            elif re.search(r'\b(?:test|todo|fixme|temp|tmp)\b', summary.lower()):
                poor_summaries[key] = {
                    "summary": summary,
                    "length": len(summary),
                    "reason": "Contains placeholder words"
                }
        
        return poor_summaries
    
    def check_epic_link_consistency(self, issues):
        """
        Check if issues linked to epics have consistent data.
        
        Args:
            issues (list): List of Jira issues
            
        Returns:
            dict: Dictionary with consistency issues
        """
        # This requires customization based on your Jira configuration
        # Here's a simple example assuming "epic" is a custom field
        epic_issues = {}
        
        for issue in issues:
            epic_link = issue["fields"].get("customfield_10008")  # Adjust field ID as needed
            if epic_link:
                if epic_link not in epic_issues:
                    epic_issues[epic_link] = []
                epic_issues[epic_link].append(issue["key"])
        
        return epic_issues
    
    def analyze_issue_cycle_time(self, issues):
        """
        Analyze the cycle time (time from creation to resolution) for issues.
        
        Args:
            issues (list): List of Jira issues
            
        Returns:
            dict: Dictionary with cycle time statistics
        """
        cycle_times = []
        
        for issue in issues:
            created_str = issue["fields"].get("created")
            resolved_str = issue["fields"].get("resolutiondate")
            
            if created_str and resolved_str:
                created_date = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                resolved_date = datetime.fromisoformat(resolved_str.replace("Z", "+00:00"))
                
                cycle_time = (resolved_date - created_date).days
                cycle_times.append({
                    "key": issue["key"],
                    "cycle_time_days": cycle_time,
                    "issue_type": issue["fields"].get("issuetype", {}).get("name")
                })
        
        if not cycle_times:
            return {"average": 0, "median": 0, "issues": []}
            
        df = pd.DataFrame(cycle_times)
        
        return {
            "average": df["cycle_time_days"].mean(),
            "median": df["cycle_time_days"].median(),
            "by_issue_type": df.groupby("issue_type")["cycle_time_days"].mean().to_dict(),
            "issues": cycle_times
        }
    
    def generate_quality_report(self, project_key, days_back=90):
        """
        Generate a comprehensive quality report for a Jira project.
        
        Args:
            project_key (str): The Jira project key
            days_back (int, optional): How many days of data to analyze
            
        Returns:
            dict: Dictionary with quality metrics and issues
        """
        since_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        jql = f"project = {project_key} AND created >= '{since_date}' ORDER BY created DESC"
        
        # Fetch issues
        issues = self.fetch_issues(jql)
        
        if not issues:
            return {"error": "No issues found for the specified project and time range"}
        
        # Required fields may vary based on your Jira workflow
        required_fields = ["summary", "description", "assignee", "priority"]
        
        report = {
            "project": project_key,
            "date_range": f"{since_date} to {datetime.now().strftime('%Y-%m-%d')}",
            "total_issues": len(issues),
            "missing_fields": self.check_missing_fields(issues, required_fields),
            "stale_issues": self.check_stale_issues(issues),
            "poor_summaries": self.check_summary_quality(issues),
            "epic_link_consistency": self.check_epic_link_consistency(issues),
            "cycle_time_analysis": self.analyze_issue_cycle_time(issues),
            "issue_type_distribution": Counter([i["fields"].get("issuetype", {}).get("name") for i in issues]),
            "status_distribution": Counter([i["fields"].get("status", {}).get("name") for i in issues])
        }
        
        # Calculate overall quality score (simple example)
        quality_score = 100
        
        # Deduct points for missing fields
        missing_fields_pct = len(report["missing_fields"]) / report["total_issues"] * 100
        quality_score -= min(30, missing_fields_pct)
        
        # Deduct points for stale issues
        stale_issues_pct = len(report["stale_issues"]) / report["total_issues"] * 100
        quality_score -= min(25, stale_issues_pct)
        
        # Deduct points for poor summaries
        poor_summaries_pct = len(report["poor_summaries"]) / report["total_issues"] * 100
        quality_score -= min(20, poor_summaries_pct)
        
        report["quality_score"] = max(0, round(quality_score, 1))
        
        return report
    
    def export_report_to_json(self, report, filename):
        """
        Export the quality report to a JSON file.
        
        Args:
            report (dict): The quality report dictionary
            filename (str): Output filename
        """
        with open(filename, 'w') as f:
            json.dump(report, f, indent=4)
    
    def export_report_to_html(self, report, filename):
        """
        Export the quality report to an HTML file.
        
        Args:
            report (dict): The quality report dictionary
            filename (str): Output filename
        """
        # This is a simple HTML export - can be enhanced with better formatting
        html = f"""
        <html>
        <head>
            <title>Jira Quality Report - {report['project']}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1, h2 {{ color: #0052CC; }}
                table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .score {{ font-size: 24px; font-weight: bold; }}
                .good {{ color: green; }}
                .medium {{ color: orange; }}
                .poor {{ color: red; }}
            </style>
        </head>
        <body>
            <h1>Jira Quality Report - {report['project']}</h1>
            <p>Date Range: {report['date_range']}</p>
            <p>Total Issues: {report['total_issues']}</p>
            
            <h2>Quality Score</h2>
            <p class="score {self._get_score_class(report['quality_score'])}">{report['quality_score']}%</p>
            
            <h2>Missing Required Fields</h2>
            <p>Issues with missing fields: {len(report['missing_fields'])}</p>
            <table>
                <tr><th>Issue Key</th><th>Missing Fields</th></tr>
                {self._generate_table_rows_from_dict(report['missing_fields'])}
            </table>
            
            <h2>Stale Issues</h2>
            <p>Stale issues (not updated in 30+ days): {len(report['stale_issues'])}</p>
            <table>
                <tr><th>Issue Key</th><th>Days Since Update</th><th>Status</th></tr>
                {self._generate_table_rows_from_list(report['stale_issues'], ['key', 'days_since_update', 'status'])}
            </table>
            
            <h2>Poor Quality Summaries</h2>
            <p>Issues with poor summaries: {len(report['poor_summaries'])}</p>
            <table>
                <tr><th>Issue Key</th><th>Summary</th><th>Reason</th></tr>
                {self._generate_table_rows_from_dict_complex(report['poor_summaries'], ['summary', 'reason'])}
            </table>
            
            <h2>Issue Type Distribution</h2>
            <table>
                <tr><th>Issue Type</th><th>Count</th></tr>
                {self._generate_table_rows_from_counter(report['issue_type_distribution'])}
            </table>
            
            <h2>Status Distribution</h2>
            <table>
                <tr><th>Status</th><th>Count</th></tr>
                {self._generate_table_rows_from_counter(report['status_distribution'])}
            </table>
            
        </body>
        </html>
        """
        
        with open(filename, 'w') as f:
            f.write(html)
    
    def _get_score_class(self, score):
        if score >= 80:
            return "good"
        elif score >= 60:
            return "medium"
        else:
            return "poor"
    
    def _generate_table_rows_from_dict(self, data):
        rows = ""
        for key, value in data.items():
            rows += f"<tr><td>{key}</td><td>{', '.join(value)}</td></tr>"
        return rows
    
    def _generate_table_rows_from_list(self, data, fields):
        rows = ""
        for item in data:
            row = "<tr>"
            for field in fields:
                row += f"<td>{item.get(field, '')}</td>"
            row += "</tr>"
            rows += row
        return rows
    
    def _generate_table_rows_from_dict_complex(self, data, fields):
        rows = ""
        for key, value in data.items():
            row = f"<tr><td>{key}</td>"
            for field in fields:
                row += f"<td>{value.get(field, '')}</td>"
            row += "</tr>"
            rows += row
        return rows
    
    def _generate_table_rows_from_counter(self, counter):
        rows = ""
        for key, count in counter.items():
            rows += f"<tr><td>{key}</td><td>{count}</td></tr>"
        return rows
    
    def visualize_quality_metrics(self, report, output_dir="."):
        """
        Create visualizations for quality metrics.
        
        Args:
            report (dict): The quality report dictionary
            output_dir (str): Directory to save visualizations
        """
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Issue type distribution
        plt.figure(figsize=(10, 6))
        issue_types = list(report['issue_type_distribution'].keys())
        counts = list(report['issue_type_distribution'].values())
        plt.bar(issue_types, counts)
        plt.title('Issue Type Distribution')
        plt.xlabel('Issue Type')
        plt.ylabel('Count')
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        plt.savefig(f"{output_dir}/issue_type_distribution.png")
        
        # Status distribution
        plt.figure(figsize=(10, 6))
        statuses = list(report['status_distribution'].keys())
        counts = list(report['status_distribution'].values())
        plt.bar(statuses, counts)
        plt.title('Status Distribution')
        plt.xlabel('Status')
        plt.ylabel('Count')
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        plt.savefig(f"{output_dir}/status_distribution.png")
        
        # Quality issues breakdown
        plt.figure(figsize=(10, 6))
        issues = [
            ('Missing Fields', len(report['missing_fields'])),
            ('Stale Issues', len(report['stale_issues'])),
            ('Poor Summaries', len(report['poor_summaries']))
        ]
        labels = [i[0] for i in issues]
        sizes = [i[1] for i in issues]
        plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
        plt.axis('equal')
        plt.title('Quality Issues Breakdown')
        plt.tight_layout()
        plt.savefig(f"{output_dir}/quality_issues_breakdown.png")


# Example usage
if __name__ == "__main__":
    # Replace with your Jira credentials
    jira_url = "https://your-domain.atlassian.net"
    username = "your-email@example.com"
    api_token = "your-api-token"
    
    checker = JiraQualityChecker(jira_url, username, api_token)
    
    # Generate report for a project
    report = checker.generate_quality_report("PROJECT")
    
    # Export report
    checker.export_report_to_json(report, "jira_quality_report.json")
    checker.export_report_to_html(report, "jira_quality_report.html")
    
    # Create visualizations
    checker.visualize_quality_metrics(report, "report_visualizations")
    
    print(f"Quality Score: {report['quality_score']}%")
    print(f"Total Issues: {report['total_issues']}")
    print(f"Issues with Missing Fields: {len(report['missing_fields'])}")
    print(f"Stale Issues: {len(report['stale_issues'])}")
    print(f"Issues with Poor Summaries: {len(report['poor_summaries'])}")
