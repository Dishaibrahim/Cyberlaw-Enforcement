import asyncio
import json
import time
from typing import Dict, Any, List, Tuple, Callable
from collections import defaultdict

# Import agents and tools from your adk_agents.py file
from .adk_agents import (
    ProsecutionLawyerAgent, DefenseLawyerAgent,
    CyberLawExpertAgent, DigitalRightsActivistAgent, SocialMediaExpertAgent,
    CourtJudgeAgent, CourtClerkAgent, firestore_tool, blockchain_tool
)

class StateManager:
    """
    Manages the shared state of the courtroom session.
    This acts as the central memory for the orchestrator and agents.
    """
    def __init__(self, initial_case_details: Dict[str, Any]):
        self.state = {
            "case_id": initial_case_details.get("id"),
            "case_details": initial_case_details, # The original flagged case details
            "transcript": [], # List of {"agent_name": str, "message": str, "type": str, "timestamp": float}
            "query_counts": defaultdict(int), # Tracks queries per agent (lawyers, experts)
            "jury_deliberation_history": [], # Log of internal jury discussions
            "jury_votes": {}, # Stores final votes from each jury member
            "final_recommendation": None, # Consensus from jury (if reached)
            "court_status": "IDLE", # Current phase of the session
            "last_agent_output": {}, # Last full output from an agent
            "current_turn_agent": None, # Name of the agent whose turn it is
            "error_message": None, # Any error that occurred during the session
            "final_verdict": None, # Final verdict from the judge
            "agents_status": { # Brief status for UI display
                "Prosecution Lawyer": "Waiting",
                "Defense Lawyer": "Waiting",
                "Cyber Law Expert": "Waiting",
                "Digital Rights Activist": "Waiting",
                "Social Media Expert": "Waiting",
                "Court Judge": "Waiting",
                "Court Clerk": "Waiting",
            }
        }

    def get_state(self) -> Dict[str, Any]:
        """Returns the current state."""
        return self.state

    def update_state(self, key: str, value: Any):
        """Updates a specific key in the state."""
        self.state[key] = value

    def add_transcript_entry(self, agent_name: str, message: str, message_type: str = "statement"):
        """Adds an entry to the public transcript."""
        self.state["transcript"].append({
            "agent_name": agent_name,
            "message": message,
            "type": message_type,
            "timestamp": time.time()
        })

    def increment_query_count(self, agent_name: str):
        """Increments the query count for a specific agent."""
        self.state["query_counts"][agent_name] += 1

    def get_query_count(self, agent_name: str) -> int:
        """Gets the current query count for an agent."""
        return self.state["query_counts"][agent_name]

    def add_jury_deliberation(self, agent_name: str, message: str):
        """Adds a deliberation point to the jury's internal history."""
        self.state["jury_deliberation_history"].append({
            "agent_name": agent_name,
            "message": message,
            "timestamp": time.time()
        })

    def record_jury_vote(self, agent_name: str, vote: str, recommendation: Dict[str, Any]):
        """Records an individual jury member's vote."""
        self.state["jury_votes"][agent_name] = {"vote": vote, "recommendation": recommendation}

    def get_transcript_summary(self, length_limit: int = 4000) -> str:
        """Returns a summarized version of the transcript for context, limited by characters."""
        full_text = "\n".join([f"{entry['agent_name']}: {entry['message']}" for entry in self.state["transcript"]])
        return full_text[-length_limit:] if len(full_text) > length_limit else full_text

    def get_jury_deliberation_summary(self, length_limit: int = 2000) -> str:
        """Returns a summarized version of jury deliberations history, limited by characters."""
        full_text = "\n".join([f"{entry['agent_name']}: {entry['message']}" for entry in self.state["jury_deliberation_history"]])
        return full_text[-length_limit:] if len(full_text) > length_limit else full_text


class CourtroomOrchestrator:
    """
    Orchestrates the multi-agent courtroom session.
    """
    def __init__(self, case_details: Dict[str, Any]):
        self.state_manager = StateManager(initial_case_details=case_details)
        self.agents = {
            "prosecution": ProsecutionLawyerAgent(),
            "defense": DefenseLawyerAgent(),
            "cyber_expert": CyberLawExpertAgent(),
            "digital_activist": DigitalRightsActivistAgent(),
            "social_media": SocialMediaExpertAgent(),
            "judge": CourtJudgeAgent(),
            "clerk": CourtClerkAgent()
        }
        self.jury_agents = [self.agents["cyber_expert"], self.agents["digital_activist"], self.agents["social_media"]]
        self.lawyer_agents = [self.agents["prosecution"], self.agents["defense"]]
        self.case_id = case_details["id"]
        self.execution_loop_task = None # To hold the asyncio task for the courtroom session

    async def _update_and_log(self, agent_obj, action_output: Dict[str, Any], message_type: str = "statement"):
        """
        Helper to update internal state and use clerk agent to log public transcript.
        """
        self.state_manager.update_state("last_agent_output", action_output)
        self.state_manager.update_state("current_turn_agent", agent_obj.name)
        self.state_manager.state["agents_status"][agent_obj.name] = "Acting"

        # Use Clerk Agent to summarize for log and transcript
        clerk_context = {
            "latest_agent_output": action_output
        }
        clerk_response = await self.agents["clerk"].act(clerk_context)
        if "error" in clerk_response:
            clerk_log_entry = f"Clerk Error: {clerk_response['error']}"
            clerk_transcript_line = f"Clerk Error: {clerk_response['error']}"
            self.state_manager.update_state("error_message", clerk_log_entry) # Log clerk errors
        else:
            clerk_log_entry = clerk_response.get("log_entry", "No log entry from clerk.")
            clerk_transcript_line = clerk_response.get("transcript_line", "No transcript line from clerk.")

        self.state_manager.add_transcript_entry(
            agent_name="Court Clerk",
            message=clerk_log_entry,
            message_type="log"
        )
        self.state_manager.add_transcript_entry(
            agent_name=agent_obj.name,
            message=clerk_transcript_line,
            message_type=message_type
        )
        self.state_manager.state["agents_status"][agent_obj.name] = "Waiting"


    async def run_courtroom_session(self):
        """
        Orchestrates the entire courtroom session through its phases.
        This is the main execution loop for the multi-agent system.
        """
        self.state_manager.update_state("court_status", "STARTING")
        self.state_manager.add_transcript_entry("Court", "Courtroom session is commencing for Case ID: " + self.case_id, "system")
        await asyncio.sleep(1) # Small delay for realism

        try:
            # --- Phase 1: Opening Statements ---
            self.state_manager.update_state("court_status", "OPENING_STATEMENTS")
            self.state_manager.add_transcript_entry("Court", "Phase 1: Opening Statements", "system")
            await asyncio.sleep(1)

            # Prosecution Opening
            prosecution_context = {"case_details": self.state_manager.get_state()["case_details"], "action_type": "opening_statement"}
            prosecution_output = await self.agents["prosecution"].act(prosecution_context)
            if "error" in prosecution_output: raise Exception(f"Prosecution Error: {prosecution_output['error']}")
            await self._update_and_log(self.agents["prosecution"], prosecution_output, "statement")
            self.state_manager.update_state("prosecution_opening_statement", prosecution_output)
            await asyncio.sleep(2)

            # Defense Opening
            defense_context = {
                "case_details": self.state_manager.get_state()["case_details"],
                "prosecution_opening_statement": self.state_manager.get_state()["prosecution_opening_statement"],
                "action_type": "rebuttal_statement"
            }
            defense_output = await self.agents["defense"].act(defense_context)
            if "error" in defense_output: raise Exception(f"Defense Error: {defense_output['error']}")
            await self._update_and_log(self.agents["defense"], defense_output, "statement")
            self.state_manager.update_state("defense_rebuttal_statement", defense_output)
            await asyncio.sleep(2)

            # --- Phase 2: Query Rounds ---
            self.state_manager.update_state("court_status", "QUERY_ROUNDS")
            self.state_manager.add_transcript_entry("Court", "Phase 2: Query Rounds (Lawyers: 2 each, Experts: 1 each)", "system")
            await asyncio.sleep(1)

            # Define query order: P1, D1, CE1, DRA1, SME1, P2, D2
            # Each tuple: (agent_object, action_type, target_agent_for_answer)
            query_order_agents_and_targets = [
                (self.agents["prosecution"], "query", self.agents["defense"]),
                (self.agents["defense"], "query", self.agents["prosecution"]),
                (self.agents["cyber_expert"], "query", self.agents["prosecution"]), # Experts ask lawyers
                (self.agents["digital_activist"], "query", self.agents["defense"]), # Experts ask lawyers
                (self.agents["social_media"], "query", self.agents["prosecution"]), # Experts ask lawyers
                (self.agents["prosecution"], "query", self.agents["defense"]), # Second query for lawyers
                (self.agents["defense"], "query", self.agents["prosecution"]),
            ]

            for agent_obj, action_type, target_agent_obj in query_order_agents_and_targets:
                if self.state_manager.get_query_count(agent_obj.name) < agent_obj.max_queries:
                    # Agent asks a question
                    query_context = {
                        "case_details": self.state_manager.get_state()["case_details"],
                        "transcript_summary": self.state_manager.get_transcript_summary(),
                        "action_type": action_type,
                        "remaining_queries": agent_obj.max_queries - self.state_manager.get_query_count(agent_obj.name)
                    }
                    query_output = await agent_obj.act(query_context)
                    if "error" in query_output: raise Exception(f"{agent_obj.name} Query Error: {query_output['error']}")
                    await self._update_and_log(agent_obj, query_output, "query")
                    query_text = query_output.get("query_text", query_output.get("content", "")) # 'content' for experts

                    # Target agent answers the question
                    if target_agent_obj:
                        answer_context = {
                            "case_details": self.state_manager.get_state()["case_details"],
                            "transcript_summary": self.state_manager.get_transcript_summary(),
                            "question_text": query_text,
                            "action_type": "answer_query"
                        }
                        answer_output = await target_agent_obj.act(answer_context)
                        if "error" in answer_output: raise Exception(f"{target_agent_obj.name} Answer Error: {answer_output['error']}")
                        await self._update_and_log(target_agent_obj, answer_output, "answer")

                    self.state_manager.increment_query_count(agent_obj.name)
                    await asyncio.sleep(2)
                else:
                    self.state_manager.add_transcript_entry(agent_obj.name, f"{agent_obj.name} has used all their queries.", "system")
                    await asyncio.sleep(0.5) # Small pause


            # --- Phase 3: Jury Deliberation ---
            self.state_manager.update_state("court_status", "JURY_DELIBERATION")
            self.state_manager.add_transcript_entry("Court", "Phase 3: Jury Deliberation begins.", "system")
            await asyncio.sleep(1)

            # Iterative deliberation (e.g., 3 rounds of discussion)
            for i in range(3):
                self.state_manager.add_transcript_entry("Court", f"Jury Deliberation Round {i+1}", "system")
                for jury_agent in self.jury_agents:
                    deliberation_context = {
                        "case_details": self.state_manager.get_state()["case_details"],
                        "full_transcript_of_all_queries_and_responses": self.state_manager.get_transcript_summary(),
                        "jury_deliberation_history_summary": self.state_manager.get_jury_deliberation_summary(),
                        "round": i + 1
                    }
                    # Prompt for deliberation. This uses the agent's LLM directly for a free-form response.
                    # You might need to refine these prompts within adk_agents.py if you want structured deliberation output.
                    jury_prompt = f"""
You are {jury_agent.name} during jury deliberation. Review the case and previous deliberation points. Provide your current thoughts or respond to another jury member's statement. Aim for consensus.

**Case Details:** {json.dumps(self.state_manager.get_state()['case_details'], indent=2)}
**Transcript Summary:** {self.state_manager.get_transcript_summary()}
**Jury Deliberation History:** {self.state_manager.get_jury_deliberation_summary()}

Provide your deliberation point.
"""
                    deliberation_output_text = await jury_agent.llm.generate_content(jury_prompt)

                    if "error" in deliberation_output_text: raise Exception(f"{jury_agent.name} Deliberation Error: {deliberation_output_text['error']}")

                    self.state_manager.add_jury_deliberation(
                        jury_agent.name,
                        deliberation_output_text # Directly use the text output
                    )
                    self.state_manager.add_transcript_entry(
                        jury_agent.name,
                        f"Deliberating: {deliberation_output_text}",
                        "deliberation"
                    )
                    await asyncio.sleep(1)
            self.state_manager.add_transcript_entry("Court", "Jury deliberation concluded.", "system")
            await asyncio.sleep(2)


            # --- Phase 4: Consensus and Voting ---
            self.state_manager.update_state("court_status", "VOTING")
            self.state_manager.add_transcript_entry("Court", "Phase 4: Jury Voting.", "system")
            await asyncio.sleep(1)

            for jury_agent in self.jury_agents:
                voting_prompt = f"""
You are {jury_agent.name} and jury member. The deliberation phase is over. Based on all the evidence, arguments, and jury discussions, cast your final vote (Guilty or Not Guilty) and provide your recommended final fine (in ETH/MATIC ether/matic units), ban status, and compensation amount. Explain your vote briefly.

**Case Details:** {json.dumps(self.state_manager.get_state()['case_details'], indent=2)}
**Full Transcript:** {self.state_manager.get_transcript_summary()}
**Jury Deliberation Summary:** {self.state_manager.get_jury_deliberation_summary()}

Provide your vote and recommendation in JSON format:
{{
    "agent_name": "{jury_agent.name}",
    "vote": "Guilty" | "Not Guilty",
    "recommendation_fine_eth": "number",
    "recommendation_ban": "string",
    "recommendation_compensation_eth": "number",
    "explanation": "string (Brief explanation for your vote)"
}}
"""
                schema = {
                    "type": "OBJECT",
                    "properties": {
                        "agent_name": {"type": "STRING"},
                        "vote": {"type": "STRING", "enum": ["Guilty", "Not Guilty"]},
                        "recommendation_fine_eth": {"type": "NUMBER"},
                        "recommendation_ban": {"type": "STRING"},
                        "recommendation_compensation_eth": {"type": "NUMBER"},
                        "explanation": {"type": "STRING"}
                    }
                }
                vote_output = await jury_agent.llm.generate_content(voting_prompt, response_schema=schema)
                if "error" in vote_output: raise Exception(f"{jury_agent.name} Voting Error: {vote_output['error']}")

                self.state_manager.record_jury_vote(
                    jury_agent.name,
                    vote_output.get("vote", "N/A"),
                    {
                        "fine_eth": vote_output.get("recommendation_fine_eth"),
                        "ban_status": vote_output.get("recommendation_ban"),
                        "compensation_eth": vote_output.get("recommendation_compensation_eth")
                    }
                )
                self.state_manager.add_transcript_entry(
                    jury_agent.name,
                    f"Voted '{vote_output.get('vote')}' with recommendation: Fine {vote_output.get('recommendation_fine_eth')} ETH, Ban '{vote_output.get('recommendation_ban')}', Compensation {vote_output.get('recommendation_compensation_eth')} ETH. Reason: {vote_output.get('explanation')}",
                    "vote"
                )
                await asyncio.sleep(1)

            # Determine majority verdict
            guilty_votes = sum(1 for v in self.state_manager.state["jury_votes"].values() if v["vote"] == "Guilty")
            not_guilty_votes = sum(1 for v in self.state_manager.state["jury_votes"].values() if v["vote"] == "Not Guilty")

            final_jury_verdict = "Undetermined"
            if guilty_votes > not_guilty_votes:
                final_jury_verdict = "Guilty"
            elif not_guilty_votes > guilty_votes:
                final_jury_verdict = "Not Guilty"
            else:
                final_jury_verdict = "Hung Jury (Tie)"

            self.state_manager.update_state("final_recommendation", final_jury_verdict)
            self.state_manager.add_transcript_entry("Court", f"Jury has cast votes. Final Jury Verdict: {final_jury_verdict}", "system")
            await asyncio.sleep(2)


            # --- Phase 5: Verdict & Sentencing (with Social Score) ---
            self.state_manager.update_state("court_status", "VERDICT_AND_SENTENCING")
            self.state_manager.add_transcript_entry("Court", "Phase 5: Judge delivers final verdict and sentencing.", "system")
            await asyncio.sleep(1)

            judge_context = {
                "case_details": self.state_manager.get_state()["case_details"],
                "transcript_full": self.state_manager.get_transcript_summary(length_limit=8000), # More context for judge
                "jury_votes": self.state_manager.state["jury_votes"],
                "jury_consensus_summary": final_jury_verdict, # Pass the aggregated jury verdict
                "victim_eth_address": self.state_manager.get_state()["case_details"].get("victimEthAddress") # Pass victim's ETH address
            }
            judge_output = await self.agents["judge"].act(judge_context)
            if "error" in judge_output: raise Exception(f"Judge Error: {judge_output['error']}")
            await self._update_and_log(self.agents["judge"], judge_output, "statement")

            self.state_manager.update_state("final_verdict", judge_output)

            # Record final verdict on Firestore (always)
            # Convert ETH amounts from LLM (ether/matic units) to Wei for Firestore/Blockchain storage
            fine_eth_from_llm = judge_output.get("final_fine_eth", 0)
            compensation_eth_from_llm = judge_output.get("final_compensation_eth", 0)

            # Ensure conversion handles potential float precision issues by rounding or using Decimal if needed
            fine_wei = int(fine_eth_from_llm * (10**18))
            compensation_wei = int(compensation_eth_from_llm * (10**18))
            
            firestore_case_update = {
                "courtroomVerdict": judge_output,
                "courtroomStatus": self.state_manager.get_state()["court_status"],
                "courtroomTranscript": self.state_manager.get_state()["transcript"],
                "finalFineWei": fine_wei, # Store in Wei
                "finalCompensationWei": compensation_wei, # Store in Wei
                "socialScore": judge_output.get("social_score"),
                "victimEthAddress": judge_output.get("victim_eth_address") # Ensure this is captured in initial case details
            }
            # Use firestore_tool to update the original case document
            fs_update_result = await firestore_tool.run(
                "set_doc",
                f"artifacts/{self.state_manager.state['case_details']['appId']}/public/data/cyberlawCases",
                self.case_id,
                firestore_case_update
            )
            self.state_manager.add_transcript_entry("Court Clerk", f"Firestore Update Result: {fs_update_result}", "log")


            # Record final verdict on Blockchain (if configured)
            if blockchain_tool.w3: # Check if blockchain tool is initialized
                blockchain_record_result = await blockchain_tool.run(
                    "record_case",
                    case_id=self.case_id,
                    postHash=hashlib.sha256(self.state_manager.get_state()["case_details"]["postContent"].encode()).hexdigest(),
                    victimAddress=judge_output.get("victim_eth_address"),
                    violationType=self.state_manager.get_state()["case_details"].get("analysis", {}).get("violationType", "N/A"),
                    councilDecision=judge_output.get("verdict_type"),
                    penaltyAmountWei=fine_wei,
                    banStatus=judge_output.get("final_ban_status"),
                    decisionExplanation=judge_output.get("explanation"),
                    compensationToVictimWei=compensation_wei,
                    socialScore=judge_output.get("social_score")
                )
                self.state_manager.add_transcript_entry("Court Clerk", f"Blockchain Record Result: {blockchain_record_result}", "log")
            else:
                self.state_manager.add_transcript_entry("Court Clerk", "Blockchain tool not initialized, skipping on-chain record.", "log")

            self.state_manager.update_state("court_status", "COMPLETED")
            self.state_manager.add_transcript_entry("Court", "Courtroom session concluded. Verdict delivered.", "system")

        except Exception as e:
            self.state_manager.update_state("error_message", str(e))
            self.state_manager.update_state("court_status", "ERROR")
            self.state_manager.add_transcript_entry("Court", f"Session ended with error: {e}", "error")
            print(f"Courtroom session error: {e}")

    def get_current_state_for_frontend(self) -> Dict[str, Any]:
        """Returns a simplified state object for the frontend."""
        state = self.state_manager.get_state()
        return {
            "case_id": state["case_id"],
            "court_status": state["court_status"],
            "current_turn_agent": state["current_turn_agent"],
            "transcript": state["transcript"],
            "jury_deliberation_history": state["jury_deliberation_history"],
            "jury_votes": state["jury_votes"],
            "final_verdict": state["final_verdict"],
            "error_message": state["error_message"],
            "agents_status": state["agents_status"]
        }
