import os
import json
import httpx
import hashlib
from typing import Dict, Any, Optional
from collections import defaultdict 


class ADKLlm:
    """
    Mimics an ADK LLM client for interacting with Gemini API.
    """
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            print("Warning: GEMINI_API_KEY environment variable not set.")

    async def generate_content(self, prompt: str, response_schema: Optional[Dict[str, Any]] = None) -> Any:
        """
        Calls the Gemini API to generate content based on the prompt and optional schema.
        """
        chat_history = [{"role": "user", "parts": [{"text": prompt}]}]
        payload = {"contents": chat_history}

        if response_schema:
            payload["generationConfig"] = {
                "responseMimeType": "application/json",
                "responseSchema": response_schema
            }

        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"

        try:
            async with httpx.AsyncClient(timeout=120.0) as client: # Increased timeout for complex prompts
                response = await client.post(api_url, json=payload)
                response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
                result = response.json()

                if result.get("candidates") and result["candidates"][0].get("content") and \
                   result["candidates"][0]["content"].get("parts") and result["candidates"][0]["content"]["parts"][0].get("text"):
                    text = result["candidates"][0]["content"]["parts"][0]["text"]
                    if response_schema:
                        try:
                            return json.loads(text)
                        except json.JSONDecodeError:
                            print(f"JSON Decode Error from LLM for schema: {text}")
                            return {"error": "LLM returned invalid JSON for schema."}
                    return text
                else:
                    return {"error": "No valid content in AI agent response."}
        except httpx.RequestError as exc:
            return {"error": f"Gemini API request failed: {exc}"}
        except httpx.HTTPStatusError as exc:
            return {"error": f"Gemini API error response (Status {exc.response.status_code}): {exc.response.text}"}
        except json.JSONDecodeError:
            return {"error": "Failed to parse Gemini API JSON response."}
        except Exception as e:
            return {"error": f"An unexpected error occurred during Gemini API call: {e}"}

class ADKTool:
    """
    Mimics an ADK Tool base class.
    """
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    async def run(self, *args, **kwargs) -> Any:
        """
        Executes the tool's functionality. Must be implemented by subclasses.
        """
        raise NotImplementedError("Tool must implement run method")

class ADKAgent:
    """
    Mimics an ADK Agent base class.
    """
    def __init__(self, name: str, description: str, llm: ADKLlm, tools: Optional[list[ADKTool]] = None, max_queries: int = 0):
        self.name = name
        self.description = description
        self.llm = llm
        self.tools = tools if tools is not None else []
        self.query_count = 0 # Tracks how many queries this agent has made in a session
        self.max_queries = max_queries # Max queries allowed for this agent

    async def act(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main method for the agent to take an action based on context.
        This is where the LLM is prompted. Must be implemented by subclasses.
        """
        raise NotImplementedError("Agent must implement act method")
# --- END Simplified ADK Mimicry ---


# --- Custom Tools for the Courtroom System ---

from web3 import Web3
from firebase_admin import firestore, credentials
import firebase_admin

# Initialize Firebase Admin SDK (for backend Firestore interaction)
# This uses GOOGLE_APPLICATION_CREDENTIALS environment variable
try:
    if not firebase_admin._apps: # Initialize only if not already initialized
        # Use ApplicationDefault credentials for GCP deployment, or file path for local
        cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Firebase Admin SDK for Firestore initialized.")
except Exception as e:
    print(f"Error initializing Firebase Admin SDK for Firestore: {e}")
    db = None # Set to None if initialization fails


# Web3.py setup (for blockchain interaction)
NODE_RPC_URL = os.getenv("NODE_RPC_URL")
TREASURY_PRIVATE_KEY = os.getenv("TREASURY_PRIVATE_KEY")
CYBERLAW_CONTRACT_ADDRESS = os.getenv("CYBERLAW_CONTRACT_ADDRESS")
CYBERLAW_CONTRACT_ABI_STR = os.getenv("CYBERLAW_CONTRACT_ABI", "[]")

w3 = None
treasury_account = None
CYBERLAW_CONTRACT_ABI = []

if all([NODE_RPC_URL, TREASURY_PRIVATE_KEY, CYBERLAW_CONTRACT_ADDRESS, CYBERLAW_CONTRACT_ABI_STR]):
    try:
        CYBERLAW_CONTRACT_ABI = json.loads(CYBERLAW_CONTRACT_ABI_STR)
        w3 = Web3(Web3.HTTPProvider(NODE_RPC_URL))
        if w3.is_connected():
            treasury_account = w3.eth.account.from_key(TREASURY_PRIVATE_KEY)
            print(f"Web3 connected. Treasury address: {treasury_account.address}")
        else:
            print("Web3 not connected. Check NODE_RPC_URL.")
            w3 = None
    except json.JSONDecodeError:
        print("Warning: Could not parse CYBERLAW_CONTRACT_ABI. Blockchain tools may fail.")
    except Exception as e:
        print(f"Error initializing Web3: {e}")
        w3 = None
else:
    print("Warning: Missing blockchain config (NODE_RPC_URL, TREASURY_PRIVATE_KEY, CYBERLAW_CONTRACT_ADDRESS, CYBERLAW_CONTRACT_ABI). Blockchain tools will be disabled.")


class FirestoreTool(ADKTool):
    """
    Tool for interacting with Firestore.
    """
    def __init__(self, db_client):
        super().__init__("firestore_access", "Accesses and updates Firestore database.")
        self.db = db_client

    async def run(self, action: str, collection_path: str, doc_id: Optional[str] = None, data: Optional[Dict[str, Any]] = None, query_filters: Optional[Dict[str, Any]] = None) -> str:
        if not self.db:
            return "Error: Firestore not initialized."
        try:
            if action == "get_doc" and doc_id:
                doc_ref = self.db.collection(collection_path).document(doc_id)
                doc = doc_ref.get() # Firestore client get() is synchronous
                if doc.exists:
                    return json.dumps(doc.to_dict())
                else:
                    return "Document not found."
            elif action == "set_doc" and doc_id and data:
                doc_ref = self.db.collection(collection_path).document(doc_id)
                doc_ref.set(data, merge=True) # Firestore client set() is synchronous
                return f"Document {doc_id} set/updated."
            elif action == "query_collection" and query_filters:
                q_ref = self.db.collection(collection_path)
                # Simple query filter application (can be extended for more complex queries)
                for field, op, value in query_filters: # e.g., ("status", "==", "Pending")
                    if op == "==":
                        q_ref = q_ref.where(field, "==", value)
                    # Add more operators as needed
                docs = q_ref.get()
                results = [doc.to_dict() for doc in docs]
                return json.dumps(results)
            else:
                return "Invalid Firestore action or missing parameters."
        except Exception as e:
            return f"Firestore tool error: {e}"


class BlockchainTool(ADKTool):
    """
    Tool for interacting with the CyberLaw blockchain ledger smart contract.
    """
    def __init__(self, w3_instance, treasury_acc, contract_addr, contract_abi):
        super().__init__("blockchain_ledger_interaction", "Interacts with the CyberLaw blockchain ledger smart contract.")
        self.w3 = w3_instance
        self.treasury_account = treasury_acc
        self.contract_address = contract_addr
        self.contract_abi = contract_abi

    async def run(self, action: str, case_id: str, **kwargs) -> str:
        if not self.w3 or not self.treasury_account or not self.contract_address or not self.contract_abi:
            return "Error: Blockchain connection not fully initialized."

        try:
            contract = self.w3.eth.contract(address=self.w3.to_checksum_address(self.contract_address), abi=self.contract_abi)
            nonce = self.w3.eth.get_transaction_count(self.treasury_account.address)
            chain_id = self.w3.eth.chain_id

            if action == "record_case":
                # Expects _postHash, _victimAddress, _violationType, _councilDecision,
                # _penaltyAmountWei, _banStatus, _decisionExplanation, _compensationToVictimWei, _socialScore
                victim_address = kwargs.get('victimAddress')
                if not self.w3.is_checksum_address(victim_address):
                    return f"Error: Invalid victim ETH address provided: {victim_address}"

                tx_hash = contract.functions.recordCase(
                    case_id,
                    kwargs.get('postHash'),
                    self.w3.to_checksum_address(victim_address),
                    kwargs.get('violationType'),
                    kwargs.get('councilDecision'),
                    kwargs.get('penaltyAmountWei'),
                    kwargs.get('banStatus'),
                    kwargs.get('decisionExplanation'),
                    kwargs.get('compensationToVictimWei'),
                    kwargs.get('socialScore')
                ).build_transaction({
                    'chainId': chain_id, 'gas': 3_000_000, # Increased gas limit
                    'maxFeePerGas': self.w3.to_wei(200, 'gwei'),
                    'maxPriorityFeePerGas': self.w3.to_wei(5, 'gwei'),
                    'nonce': nonce,
                })
                signed_tx = self.w3.eth.account.sign_transaction(tx_hash, private_key=TREASURY_PRIVATE_KEY)
                tx_sent = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_sent, timeout=120) # Wait longer
                if receipt.status == 1:
                    return f"Case recorded on blockchain. TX Hash: {receipt.transactionHash.hex()}"
                else:
                    return f"Blockchain transaction failed. TX Hash: {receipt.transactionHash.hex()}"

            elif action == "distribute_compensation":
                tx_hash = contract.functions.distributeCompensation(case_id).build_transaction({
                    'chainId': chain_id, 'gas': 1_000_000,
                    'maxFeePerGas': self.w3.to_wei(200, 'gwei'),
                    'maxPriorityFeePerGas': self.w3.to_wei(5, 'gwei'),
                    'nonce': nonce,
                })
                signed_tx = self.w3.eth.account.sign_transaction(tx_hash, private_key=TREASURY_PRIVATE_KEY)
                tx_sent = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_sent, timeout=120)
                if receipt.status == 1:
                    return f"Compensation distributed. TX Hash: {receipt.transactionHash.hex()}"
                else:
                    return f"Compensation distribution failed. TX Hash: {receipt.transactionHash.hex()}"

            elif action == "get_case_on_chain":
                case_data = contract.functions.getCase(case_id).call()
                # Convert tuple to dict or more readable format
                return json.dumps({
                    "caseId": case_data[0], "postHash": case_data[1], "victimAddress": case_data[2],
                    "violationType": case_data[3], "councilDecision": case_data[4],
                    "penaltyAmountWei": case_data[5], "banStatus": case_data[6],
                    "decisionExplanation": case_data[7], "compensationToVictimWei": case_data[8],
                    "socialScore": case_data[9], "fineCollected": case_data[10],
                    "compensationDistributed": case_data[11], "timestamp": case_data[12]
                })

            else:
                return "Invalid blockchain action."
        except Exception as e:
            return f"Blockchain tool error: {e}"


# --- Agent Definitions ---

# Initialize a single LLM instance for all agents to share
gemini_llm = ADKLlm(model_name="gemini-2.0-flash")

# Initialize common tools
firestore_tool = FirestoreTool(db)
blockchain_tool = BlockchainTool(w3, treasury_account, CYBERLAW_CONTRACT_ADDRESS, CYBERLAW_CONTRACT_ABI)


class ProsecutionLawyerAgent(ADKAgent):
    def __init__(self):
        super().__init__(
            name="Prosecution Lawyer",
            description="You are the Prosecution Lawyer in a cyber law court session. Your objective is to present a strong opening statement, clearly outlining the case against the defendant, citing relevant cyber law types, and detailing the alleged violation based on the provided evidence. Conclude by clearly stating your initial proposed penalty (a specific amount in ETH/MATIC ether/matic units, a ban status, and potential compensation for the victim). Your tone should be formal, assertive, and focused on facts and legal arguments. You also get two opportunities to ask follow-up questions.",
            llm=gemini_llm,
            tools=[firestore_tool], # Can access case details from Firestore
            max_queries=2
        )

    async def act(self, context: Dict[str, Any]) -> Dict[str, Any]:
        prompt = ""
        action_type = context.get("action_type", "opening_statement") # 'opening_statement', 'query', 'answer'

        if action_type == "opening_statement":
            prompt = f"""
You are the Prosecution Lawyer in a cyber law court session. Your objective is to present a strong opening statement, clearly outlining the case against the defendant, citing relevant cyber law types, and detailing the alleged violation based on the provided evidence. Conclude by clearly stating your initial proposed penalty (a specific amount in ETH/MATIC ether/matic units, a ban status, and potential compensation for the victim). Your tone should be formal, assertive, and focused on facts and legal arguments.

**Case Details:**
{json.dumps(context.get('case_details', {}), indent=2)}

Provide your opening statement in JSON format with the following schema:
{{
    "statement_type": "opening_statement",
    "agent_name": "Prosecution Lawyer",
    "statement_text": "string (Your compelling opening argument)",
    "proposed_fine_eth": "number (amount in ETH/MATIC, e.g., 0.5, 1.2)",
    "proposed_ban_status": "string (e.g., 'Temporary', 'Permanent', 'None')",
    "proposed_compensation_eth": "number (amount for victim in ETH/MATIC, e.g., 0.4, 0.96)"
}}
"""
            schema = {
                "type": "OBJECT",
                "properties": {
                    "statement_type": {"type": "STRING"},
                    "agent_name": {"type": "STRING"},
                    "statement_text": {"type": "STRING"},
                    "proposed_fine_eth": {"type": "NUMBER"},
                    "proposed_ban_status": {"type": "STRING"},
                    "proposed_compensation_eth": {"type": "NUMBER"}
                }
            }
        elif action_type == "query":
            # Ensure query_count is managed by orchestrator, not self.query_count directly here for ADK compliance
            prompt = f"""
You are the Prosecution Lawyer. You are currently in a query round. Your goal is to ask a precise and insightful question to gather more information or challenge the defense/witnesses, within your allocated {context.get('remaining_queries', 0)} remaining queries. Focus on aspects that strengthen your case.

**Case Details:**
{json.dumps(context.get('case_details', {}), indent=2)}
**Current Transcript Summary:**
{context.get('transcript_summary', '')}
**Last statement from opponent/witness (if any):**
{context.get('last_statement', '')}

Provide your question in JSON format with the following schema:
{{
    "statement_type": "query",
    "agent_name": "Prosecution Lawyer",
    "query_text": "string (Your specific question)"
}}
"""
            schema = {
                "type": "OBJECT",
                "properties": {
                    "statement_type": {"type": "STRING"},
                    "agent_name": {"type": "STRING"},
                    "query_text": {"type": "STRING"}
                }
            }
        elif action_type == "answer_query":
            prompt = f"""
You are the Prosecution Lawyer. You have been asked a question. Provide a concise and factual answer that supports your case, drawing on the case details and your legal arguments.

**Case Details:**
{json.dumps(context.get('case_details', {}), indent=2)}
**Question asked:**
{context.get('question_text', '')}
**Current Transcript Summary:**
{context.get('transcript_summary', '')}

Provide your answer in JSON format with the following schema:
{{
    "statement_type": "answer",
    "agent_name": "Prosecution Lawyer",
    "answer_text": "string (Your concise answer)"
}}
"""
            schema = {
                "type": "OBJECT",
                "properties": {
                    "statement_type": {"type": "STRING"},
                    "agent_name": {"type": "STRING"},
                    "answer_text": {"type": "STRING"}
                }
            }
        else:
            return {"error": "Invalid action_type for Prosecution Lawyer."}

        return await self.llm.generate_content(prompt, response_schema=schema)


class DefenseLawyerAgent(ADKAgent):
    def __init__(self):
        super().__init__(
            name="Defense Lawyer",
            description="You are the Defense Lawyer in this cyber law court session. Your task is to deliver a robust rebuttal to the Prosecution's opening statement. Carefully analyze their arguments and evidence. Your goal is to sow doubt, highlight mitigating circumstances, argue for the defendant's innocence, or advocate for a significantly reduced penalty. Your tone should be professional, skeptical of the prosecution's claims, and focused on protecting your client's interests. You also get two opportunities to ask follow-up questions.",
            llm=gemini_llm,
            tools=[firestore_tool], # Can access case details
            max_queries=2
        )

    async def act(self, context: Dict[str, Any]) -> Dict[str, Any]:
        prompt = ""
        action_type = context.get("action_type", "rebuttal_statement")

        if action_type == "rebuttal_statement":
            prompt = f"""
You are the Defense Lawyer in this cyber law court session. Your task is to deliver a robust rebuttal to the Prosecution's opening statement. Carefully analyze their arguments and evidence. Your goal is to sow doubt, highlight mitigating circumstances, argue for the defendant's innocence, or advocate for a significantly reduced penalty. Your tone should be professional, skeptical of the prosecution's claims, and focused on protecting your client's interests.

**Case Details:**
{json.dumps(context.get('case_details', {}), indent=2)}

**Prosecution's Opening Statement:**
{json.dumps(context.get('prosecution_opening_statement', {}), indent=2)}

Provide your rebuttal statement in JSON format with the following schema:
{{
    "statement_type": "rebuttal_statement",
    "agent_name": "Defense Lawyer",
    "statement_text": "string (Your persuasive rebuttal argument)",
    "counter_proposal_fine_eth": "number (e.g., 0 for innocence, or a lower amount)",
    "counter_proposal_ban_status": "string (e.g., 'None', 'Community Service')",
    "counter_proposal_compensation_eth": "number (e.g., 0)"
}}
"""
            schema = {
                "type": "OBJECT",
                "properties": {
                    "statement_type": {"type": "STRING"},
                    "agent_name": {"type": "STRING"},
                    "statement_text": {"type": "STRING"},
                    "counter_proposal_fine_eth": {"type": "NUMBER"},
                    "counter_proposal_ban_status": {"type": "STRING"},
                    "counter_proposal_compensation_eth": {"type": "NUMBER"}
                }
            }
        elif action_type == "query":
            prompt = f"""
You are the Defense Lawyer. You are currently in a query round. Your goal is to ask a precise and insightful question to gather more information or challenge the prosecution/witnesses, within your allocated {context.get('remaining_queries', 0)} remaining queries. Focus on aspects that weaken the prosecution's case or strengthen your defense.

**Case Details:**
{json.dumps(context.get('case_details', {}), indent=2)}
**Current Transcript Summary:**
{context.get('transcript_summary', '')}
**Last statement from opponent/witness (if any):**
{context.get('last_statement', '')}

Provide your question in JSON format with the following schema:
{{
    "statement_type": "query",
    "agent_name": "Defense Lawyer",
    "query_text": "string (Your specific question)"
}}
"""
            schema = {
                "type": "OBJECT",
                "properties": {
                    "statement_type": {"type": "STRING"},
                    "agent_name": {"type": "STRING"},
                    "query_text": {"type": "STRING"}
                }
            }
        elif action_type == "answer_query":
            prompt = f"""
You are the Defense Lawyer. You have been asked a question. Provide a concise and factual answer that supports your client's defense, drawing on the case details and your legal arguments.

**Case Details:**
{json.dumps(context.get('case_details', {}), indent=2)}
**Question asked:**
{context.get('question_text', '')}
**Current Transcript Summary:**
{context.get('transcript_summary', '')}

Provide your answer in JSON format with the following schema:
{{
    "statement_type": "answer",
    "agent_name": "Defense Lawyer",
    "answer_text": "string (Your concise answer)"
}}
"""
            schema = {
                "type": "OBJECT",
                "properties": {
                    "statement_type": {"type": "STRING"},
                    "agent_name": {"type": "STRING"},
                    "answer_text": {"type": "STRING"}
                }
            }
        else:
            return {"error": "Invalid action_type for Defense Lawyer."}

        return await self.llm.generate_content(prompt, response_schema=schema)


class CyberLawExpertAgent(ADKAgent):
    def __init__(self):
        super().__init__(
            name="Cyber Law Expert",
            description="You are the Cyber Law Expert serving as a jury/council member. Based on the case details and the arguments presented by both the Prosecution and Defense, provide an objective assessment of the legal and technical aspects. Clarify any ambiguities, point out specific legal precedents (simulated), or ask a technical question crucial for your deliberation. Your tone should be impartial, analytical, and authoritative. You get one opportunity to ask a question.",
            llm=gemini_llm,
            tools=[firestore_tool],
            max_queries=1 # One query
        )

    async def act(self, context: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"""
You are the Cyber Law Expert serving as a jury/council member. Based on the case details and the arguments presented by both the Prosecution and Defense, provide an objective assessment of the legal and technical aspects. Clarify any ambiguities, point out specific legal precedents (simulated), or ask a technical question crucial for your deliberation. Your tone should be impartial, analytical, and authoritative. You get one opportunity to ask a question.

**Case Details:**
{json.dumps(context.get('case_details', {}), indent=2)}

**Summary of Arguments Heard So Far:**
{context.get('transcript_summary', '')}

Choose one action (either an assessment or a question). If you ask a question, ensure it is clear and specific. If you provide an assessment, summarize your current view on the case's legal/technical merits. Provide your response in JSON format with the following schema:
{{
    "agent_name": "Cyber Law Expert",
    "action_type": "assessment" | "question",
    "content": "string (Your detailed legal assessment or specific technical question related to cyber law)"
}}
"""
        schema = {
            "type": "OBJECT",
            "properties": {
                "agent_name": {"type": "STRING"},
                "action_type": {"type": "STRING", "enum": ["assessment", "question"]},
                "content": {"type": "STRING"}
            }
        }
        return await self.llm.generate_content(prompt, response_schema=schema)


class DigitalRightsActivistAgent(ADKAgent):
    def __init__(self):
        super().__init__(
            name="Digital Rights Activist",
            description="You are the Digital Rights Activist serving as a jury/council member. Your focus is on safeguarding user privacy, freedom of speech, and preventing any form of digital overreach or disproportionate punishment. Based on the arguments, identify potential ethical concerns, disproportionate aspects of proposed penalties, or areas where individual rights might be at risk. You may choose to ask a question to clarify. Your tone should be empathetic, critical when necessary, and advocating for user liberties. You get one opportunity to ask a question.",
            llm=gemini_llm,
            tools=[],
            max_queries=1 # One query
        )

    async def act(self, context: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"""
You are the Digital Rights Activist serving as a jury/council member. Your focus is on safeguarding user privacy, freedom of speech, and preventing any form of digital overreach or disproportionate punishment. Based on the arguments, identify potential ethical concerns, disproportionate aspects of proposed penalties, or areas where individual rights might be at risk. You may choose to ask a question to clarify. Your tone should be empathetic, critical when necessary, and advocating for user liberties. You get one opportunity to ask a question.

**Case Details:**
{json.dumps(context.get('case_details', {}), indent=2)}

**Summary of Arguments Heard So Far:**
{context.get('transcript_summary', '')}

Choose one action (either an ethical critique/assessment or a question). If you ask a question, ensure it is clear and specific. If you provide an assessment, summarize your current view on the case's ethical implications. Provide your response in JSON format with the following schema:
{{
    "agent_name": "Digital Rights Activist",
    "action_type": "critique" | "question",
    "content": "string (Your ethical assessment or question regarding digital rights implications)"
}}
"""
        schema = {
            "type": "OBJECT",
            "properties": {
                "agent_name": {"type": "STRING"},
                "action_type": {"type": "STRING", "enum": ["critique", "question"]},
                "content": {"type": "STRING"}
            }
        }
        return await self.llm.generate_content(prompt, response_schema=schema)


class SocialMediaExpertAgent(ADKAgent):
    def __init__(self):
        super().__init__(
            name="Social Media Expert",
            description="You are the Social Media Expert serving as a jury/council member. Your expertise lies in understanding online community norms, platform policies, and the real-world impact of digital content. Analyze the flagged post and arguments through the lens of typical social media behavior, platform terms of service (simulated), and how the content might be perceived or spread online. You may ask a clarifying question. Your tone should be insightful and practical regarding online dynamics. You get one opportunity to ask a question.",
            llm=gemini_llm,
            tools=[],
            max_queries=1 # One query
        )

    async def act(self, context: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"""
You are the Social Media Expert serving as a jury/council member. Your expertise lies in understanding online community norms, platform policies, and the real-world impact of digital content. Analyze the flagged post and arguments through the lens of typical social media behavior, platform terms of service (simulated), and how the content might be perceived or spread online. You may ask a clarifying question. Your tone should be insightful and practical regarding online dynamics. You get one opportunity to ask a question.

**Case Details:**
{json.dumps(context.get('case_details', {}), indent=2)}

**Summary of Arguments Heard So Far:**
{context.get('transcript_summary', '')}

Choose one action (either a contextual assessment or a question). If you ask a question, ensure it is clear and specific. If you provide an assessment, summarize your current view on the case's social media context. Provide your response in JSON format with the following schema:
{{
    "agent_name": "Social Media Expert",
    "action_type": "assessment" | "question",
    "content": "string (Your contextual assessment or question regarding social media dynamics)"
}}
"""
        schema = {
            "type": "OBJECT",
            "properties": {
                "agent_name": {"type": "STRING"},
                "action_type": {"type": "STRING", "enum": ["assessment", "question"]},
                "content": {"type": "STRING"}
            }
        }
        return await self.llm.generate_content(prompt, response_schema=schema)


class CourtJudgeAgent(ADKAgent):
    def __init__(self):
        super().__init__(
            name="Court Judge",
            description="You are the judge presiding over the court session. Your role is to manage the procedure, ensure fairness, and issue a final ruling based on presented arguments and jury's input. You will also assign a 'social score' to the 'bad actor' (defendant) from 0-100, where 0 is the worst societal impact and 100 is no negative impact. This score should reflect the severity of the offense and its potential harm.",
            llm=gemini_llm,
            tools=[blockchain_tool, firestore_tool] # Can record verdict on chain and in Firestore
        )

    async def act(self, context: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"""
You are the Court Judge presiding over this cyber law session. You have heard all arguments from the Prosecution and Defense, and received the deliberations and votes from the jury/council. Your final task is to synthesize all information, make a definitive ruling (Guilty or Not Guilty), and issue a final sentence including the real penalty amount (in ETH/MATIC ether/matic units), a ban status, and the victim's compensation amount. You will also assign a 'social score' to the 'bad actor' (defendant) from 0-100, where 0 represents the most severe negative societal impact and 100 represents no negative societal impact. The social score should reflect the severity of the offense, harm to victim, ban status, and ethical considerations. Your tone must be formal, impartial, and authoritative. Provide a clear explanation for your decision and the social score.

**Case Details:**
{json.dumps(context.get('case_details', {}), indent=2)}

**Full Courtroom Transcript:**
{context.get('transcript_full', '')}

**Jury's Votes and Recommendations:**
{json.dumps(context.get('jury_votes', {}), indent=2)}

**Jury's Final Consensus/Recommendation:**
{context.get('jury_consensus_summary', 'No specific consensus reached.')}

Provide your final verdict and sentence in JSON format with the following schema:
{{
    "agent_name": "Court Judge",
    "verdict_type": "Guilty" | "Not Guilty",
    "final_fine_eth": "number (amount in ETH/MATIC ether/matic units, e.g., 0.75, 1.5)",
    "final_ban_status": "string (e.g., 'Permanent', 'Temporary', 'None', 'Warning')",
    "final_compensation_eth": "number (amount for victim in ETH/MATIC ether/matic units, e.g., 0.6, 1.2)",
    "explanation": "string (A concise explanation of the decision, summarizing key factors)",
    "social_score": "number (integer between 0 and 100)",
    "social_score_explanation": "string (Brief justification for the social score)",
    "victim_eth_address": "string (The Ethereum/Polygon wallet address of the victim from case_details, e.g., '0x...')"
}}
"""
        schema = {
            "type": "OBJECT",
            "properties": {
                "agent_name": {"type": "STRING"},
                "verdict_type": {"type": "STRING", "enum": ["Guilty", "Not Guilty"]},
                "final_fine_eth": {"type": "NUMBER"},
                "final_ban_status": {"type": "STRING"},
                "final_compensation_eth": {"type": "NUMBER"},
                "explanation": {"type": "STRING"},
                "social_score": {"type": "NUMBER", "minimum": 0, "maximum": 100},
                "social_score_explanation": {"type": "STRING"},
                "victim_eth_address": {"type": "STRING"}
            }
        }
        return await self.llm.generate_content(prompt, response_schema=schema)


class CourtClerkAgent(ADKAgent):
    def __init__(self):
        super().__init__(
            name="Court Clerk",
            description="You are the Court Clerk. Your task is to meticulously record and summarize the latest action or statement made in the courtroom session. This summary should be concise but capture the essence of what transpired. You also maintain the full transcript. Your tone should be objective and factual.",
            llm=gemini_llm,
            tools=[]
        )

    async def act(self, context: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"""
You are the Court Clerk. Your task is to meticulously record and summarize the latest action or statement made in the courtroom session for a running log, and also extract the key public-facing line for the official transcript. Your tone should be objective and factual.

**Latest Agent Output (JSON):**
{json.dumps(context.get('latest_agent_output', {}), indent=2)}

Provide your summary in JSON format with the following schema:
{{
    "agent_name": "Court Clerk",
    "log_entry": "string (A brief, factual summary of the latest action, e.g., 'Prosecution presented opening statement')",
    "transcript_line": "string (The concise public-facing line, e.g., 'Prosecution: The defendant's actions clearly constitute defamation.')"
}}
"""
        schema = {
            "type": "OBJECT",
            "properties": {
                "agent_name": {"type": "STRING"},
                "log_entry": {"type": "STRING"},
                "transcript_line": {"type": "STRING"}
            }
        }
        return await self.llm.generate_content(prompt, response_schema=schema)

