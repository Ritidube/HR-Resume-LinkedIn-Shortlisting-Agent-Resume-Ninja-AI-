## Security Risk Mitigation
To address potential security risks, the following mitigations have been implemented:
* Prompt injection risks are mitigated by using input validation to sanitize and structure user inputs, ensuring that only expected formats are accepted.
* Data privacy and PII risks are addressed by limiting logging of sensitive information and using secure storage for user data, with sensitive values stored in `.env` files.
* API key exposure risks are reduced by storing API keys in `.env` files, which are not committed to version control, and 
  * using environment variables to access these keys.
* Hallucination risks are mitigated by using structured outputs from the LLM, which help to identify and filter out potentially inaccurate information.
* Unauthorized access risks are mitigated by implementing secure authentication mechanisms and limiting access to authorized personnel, 
  * with access logs regularly reviewed to detect potential security breaches.