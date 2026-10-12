"""
TIMEVERSE Gemini AI Provider
Native Google Gemini conversational integration with dynamic tool calling,
multi-turn reasoning, and deterministic constraint-engine grounding.
"""

import asyncio
import json
import logging
import os
from typing import Any, Callable

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

PRIMARY_MODEL = "gemini-flash-latest"
FALLBACK_MODEL = "gemini-flash-lite-latest"


class GeminiAIProvider:
    """
    Real AI Provider integration using Google Gemini REST API.
    Features:
    - Multi-turn conversation handling
    - Native tool calling / function calling with real backend database tools
    - Preservation of thought signatures in tool responses
    - Automatic fallback between models if demand spikes occur
    - Never fakes AI output or bypasses the deterministic constraint solver
    """

    @classmethod
    def get_api_key(cls) -> str | None:
        return os.getenv("GEMINI_API_KEY") or settings.GEMINI_API_KEY

    @classmethod
    def get_provider_status(cls) -> dict[str, Any]:
        key = cls.get_api_key()
        has_key = bool(key and key.strip())
        return {
            "provider": "Google Gemini",
            "model": settings.GEMINI_MODEL or PRIMARY_MODEL,
            "fallback_model": FALLBACK_MODEL,
            "is_configured": has_key,
            "tool_calling_supported": True,
            "engine": "Google OR-Tools CP-SAT (Deterministic Constraint Engine)",
            "status_text": (
                f"Google Gemini ({settings.GEMINI_MODEL or PRIMARY_MODEL}) Active with Real Database Tools"
                if has_key
                else "Google Gemini API Key Not Configured (Server Environment Setup Required)"
            ),
            "configuration_guide": (
                "Google Gemini is configured via GEMINI_API_KEY in backend/.env.\n"
                "Live model handles natural language intent & tool selection, while\n"
                "Google OR-Tools CP-SAT guarantees 100% clash-free mathematical validity."
            ),
        }

    @classmethod
    async def chat_with_tools(
        cls,
        user_message: str,
        conversation_history: list[dict[str, str]],
        system_instruction: str,
        tool_declarations: list[dict[str, Any]],
        tool_executor: Any,
        preferred_model: str | None = None,
    ) -> dict[str, Any]:
        """
        Executes a real conversational turn with Google Gemini, dynamically resolving tool calls.
        """
        api_key = cls.get_api_key()
        if not api_key or not api_key.strip():
            return {
                "reply": (
                    "⚠️ **Google Gemini AI is not configured.**\n\n"
                    "Please provide a valid `GEMINI_API_KEY` in `backend/.env` to enable live natural-language intelligence. "
                    "Core deterministic features (such as Timetable Planner, Smart Rescheduler, and CP-SAT Solver) remain fully functional offline."
                ),
                "tools_called": [],
                "proposed_action": None,
                "provider_info": cls.get_provider_status(),
                "is_error": True,
            }

        models_to_try = [
            preferred_model or settings.GEMINI_MODEL or PRIMARY_MODEL,
            FALLBACK_MODEL,
        ]
        # Remove duplicates preserving order
        models_to_try = list(dict.fromkeys(models_to_try))

        tools_spec = [{"function_declarations": tool_declarations}]

        # Prepare initial contents from history
        contents: list[dict[str, Any]] = []
        for msg in conversation_history[-8:]:  # keep last 8 turns for bounded context
            role = "user" if msg.get("role") == "user" else "model"
            text_val = msg.get("content", "").strip()
            if text_val:
                contents.append({"role": role, "parts": [{"text": text_val}]})

        # Append current user instruction
        contents.append({"role": "user", "parts": [{"text": user_message}]})

        tools_called: list[dict[str, Any]] = []
        captured_proposed_action: dict[str, Any] | None = None

        last_error_msg = ""

        for model_name in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key.strip()}"

            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    for iteration in range(4):  # Max 4 tool hops per turn
                        payload = {
                            "system_instruction": {"parts": [{"text": system_instruction}]},
                            "contents": contents,
                            "tools": tools_spec,
                            "generationConfig": {
                                "temperature": 0.2,
                                "maxOutputTokens": 2048,
                            },
                        }

                        resp = await client.post(url, json=payload)

                        if resp.status_code == 503 or resp.status_code == 429:
                            last_error_msg = f"{model_name} returned HTTP {resp.status_code} ({resp.text[:120]})"
                            logger.warning("Gemini model %s transient error (%d), checking fallback: %s", model_name, resp.status_code, resp.text)
                            break  # Try fallback model

                        if resp.status_code != 200:
                            last_error_msg = f"Gemini API returned error {resp.status_code}: {resp.text[:200]}"
                            logger.error("Gemini API call failed (%d): %s", resp.status_code, resp.text)
                            break

                        resp_json = resp.json()
                        candidates = resp_json.get("candidates", [])
                        if not candidates:
                            last_error_msg = "Gemini returned no response candidates."
                            break

                        candidate = candidates[0]
                        candidate_content = candidate.get("content", {})
                        parts = candidate_content.get("parts", [])

                        # Check for functionCall
                        fn_call_part = next((p for p in parts if "functionCall" in p), None)

                        if fn_call_part:
                            fn_call = fn_call_part["functionCall"]
                            fn_name = fn_call.get("name")
                            fn_args = fn_call.get("args") or {}

                            logger.info("Executing Gemini tool: %s with args: %s", fn_name, fn_args)
                            tool_result = await tool_executor.execute(fn_name, fn_args)

                            # Record execution for transparency
                            tools_called.append({
                                "tool_name": fn_name,
                                "arguments": fn_args,
                                "summary": tool_result.get("summary") or tool_result.get("message") or f"Executed {fn_name}",
                            })

                            # Check if tool produced a proposed action card
                            if "proposed_action" in tool_result and not captured_proposed_action:
                                captured_proposed_action = tool_result["proposed_action"]

                            # Append model's response (preserves thoughtSignature)
                            contents.append(candidate_content)

                            # Append functionResponse from user role
                            contents.append({
                                "role": "user",
                                "parts": [
                                    {
                                        "functionResponse": {
                                            "name": fn_name,
                                            "response": {
                                                "name": fn_name,
                                                "content": tool_result,
                                            },
                                        }
                                    }
                                ],
                            })
                            # Loop to let Gemini synthesize natural response
                            continue

                        # Text response reached
                        text_parts = [p.get("text", "") for p in parts if "text" in p]
                        final_reply = "".join(text_parts).strip()

                        if final_reply:
                            return {
                                "reply": final_reply,
                                "tools_called": tools_called,
                                "proposed_action": captured_proposed_action,
                                "provider_info": {
                                    **cls.get_provider_status(),
                                    "model_used": model_name,
                                },
                                "is_error": False,
                            }
                        else:
                            last_error_msg = "Gemini returned an empty text response."
                            break

            except httpx.TimeoutException:
                last_error_msg = f"Request to Gemini ({model_name}) timed out after 30 seconds."
                logger.warning("Gemini timeout on %s", model_name)
                continue
            except Exception as exc:
                last_error_msg = f"Network or processing error with Gemini ({model_name}): {str(exc)}"
                logger.exception("Gemini call exception: %s", exc)
                continue

        # If all models failed
        return {
            "reply": (
                f"⚠️ **Google Gemini AI Service Temporarily Unavailable**\n\n"
                f"The AI assistant encountered a communication error with Google Gemini:\n"
                f"> {last_error_msg or 'High service demand or connectivity failure.'}\n\n"
                "**What you can do:**\n"
                "- Verify your `GEMINI_API_KEY` in `backend/.env`\n"
                "- Check internet connectivity to `generativelanguage.googleapis.com`\n"
                "- Try your question again in a few moments\n"
                "- You can continue creating and editing timetables directly in the **Timetable Planner** (`/timetables`)."
            ),
            "tools_called": tools_called,
            "proposed_action": captured_proposed_action,
            "provider_info": cls.get_provider_status(),
            "is_error": True,
        }

    @classmethod
    async def answer_academic_query(
        cls,
        prompt: str,
        context: str = "",
    ) -> str | None:
        """
        Generates a direct response using Google Gemini for academic/guide queries.
        """
        api_key = cls.get_api_key()
        if not api_key or not api_key.strip():
            return None

        models_to_try = [
            settings.GEMINI_MODEL or PRIMARY_MODEL,
            FALLBACK_MODEL,
        ]
        models_to_try = list(dict.fromkeys(models_to_try))

        full_prompt = prompt
        if context:
            full_prompt = f"Context:\n{context}\n\nTask:\n{prompt}"

        for model_name in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key.strip()}"
            try:
                async with httpx.AsyncClient(timeout=25.0) as client:
                    payload = {
                        "contents": [{"role": "user", "parts": [{"text": full_prompt}]}],
                        "generationConfig": {
                            "temperature": 0.2,
                            "maxOutputTokens": 1024,
                        },
                    }
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        candidates = resp.json().get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            text = "".join(p.get("text", "") for p in parts if "text" in p).strip()
                            if text:
                                return text
                    logger.warning("Gemini query failed on %s (%d): %s", model_name, resp.status_code, resp.text[:120])
            except Exception as e:
                logger.warning("Gemini query exception on %s: %s", model_name, e)
                continue
        return None
