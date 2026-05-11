## Security Risk Mitigation
To address potential security risks, the following mitigations have been implemented:
* Prompt injection risks are mitigated by using input validation to sanitize and structure user inputs, ensuring that only expected formats are accepted.
* Data privacy and PII risks are addressed by limiting logging of sensitive information and using secure storage for any temporarily required PII, with access controls in place.
* API key exposure risks are reduced by storing sensitive keys in a `.env` file, which is not committed to version control, and 
  * using environment variables to access these keys in the application.
* Hallucination risk is mitigated through the use of structured outputs from the LLM, which helps to identify and filter out potentially inaccurate or misleading information.
* Unauthorized access risks are mitigated through secure authentication and authorization mechanisms, ensuring that only authorized users can interact with the HR Resume Shortlisting Agent.