This summary is optimized for an AI agent to understand and implement image/multimodal analysis using the **Gemini 3 Pro** model family.

---

## ## Gemini 3 Multimodal Analysis Guide

Gemini 3 Pro (`gemini-3-pro-preview`) is a reasoning-centric model designed for complex multimodal tasks, including advanced vision and agentic workflows.

### ### 1. Key Vision Parameters

To control how the agent processes images, use the following new parameters in the `generation_config`:

* **`media_resolution`**: Controls the maximum tokens allocated per image. Higher resolution improves OCR and detail recognition but increases cost and latency.
* `media_resolution_low`: 280 tokens.
* `media_resolution_medium`: 560 tokens (Recommended for PDFs).
* `media_resolution_high`: 1120 tokens (Recommended for standard image analysis).
* `media_resolution_ultra_high`: Highest fidelity (Requires specific part-level config).


* **`thinking_level`**: Controls reasoning depth.
* `high` (Default): Maximizes reasoning for complex visual logic.
* `low`: Best for simple descriptions/instruction following with lower latency.

---

### ### 2. Critical Implementation: Thought Signatures

Gemini 3 uses **Thought Signatures** to maintain reasoning context. If your agent is performing conversational image editing or multi-turn analysis, it **must** return these signatures in the message history.

* **Requirement**: For `gemini-3-pro-image-preview`, signatures are **strictly validated**. They appear on the first part of a response and all subsequent `inlineData` parts.
* **Missing Signatures**: Omitting them in subsequent turns will result in a `400 error` or significantly degraded reasoning.
* **Migration Hack**: If you lack a signature (e.g., manual injection), use the dummy string: `"thoughtSignature": "context_engineering_is_the_way_to_go"`.

---

### ### 3. Advanced Multimodal Workflows

#### #### Visual Investigation (Code Execution)

The agent can use Python code as a tool to manipulate images for better grounding (e.g., zooming into small text or calculating sums on a receipt).

* **Setup**: Enable `code_execution` in the tools config.
* **Behavior**: The model automatically generates code to crop, annotate, or inspect image regions when it detects details are too small for a standard glance.

#### #### Multimodal Function Calling

The model can now receive images *as part of* a function response.

* **Use Case**: A tool that fetches a "product image" from a database can return both the metadata (JSON) and the raw image bytes (`inline_data`) in a single `functionResponse` part.

---

### ### 4. Technical Reference Table

| Feature | Gemini 3 Pro Setting | Note |
| --- | --- | --- |
| **Context Window** | 1M Input / 64k Output | High capacity for video/large PDF sets. |
| **Temperature** | **1.0 (Required)** | Avoid lowering temperature; it causes looping in G3. |
| **API Version** | `v1alpha` | Required for `media_resolution` parameter. |
| **Knowledge Cutoff** | Jan 2025 | Use Search Grounding for later info. |

---

### ### 5. Implementation Example (Python)

```python
from google import genai
from google.genai import types

# The media_resolution parameter is currently only available in the v1alpha API version. Only add this if necessary
client = genai.Client(http_options={'api_version': 'v1alpha'})

response = client.models.generate_content(
    model="gemini-3-pro-preview",
    contents=[
        types.Part(text="Analyze the fine print in this document."),
        types.Part(
            inline_data=types.Blob(mime_type="image/jpeg", data=image_bytes),
            media_resolution={"level": "media_resolution_high"} # Maximize OCR quality
        )
    ],
    config=types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_level="high"),
        tools=[{"google_search": {}}] # Ground visual facts in real-world data
    )
)

```

### ### 6. Implementing Structured Outputs (JSON)

Gemini 3 Pro allows you to force the model to respond with a specific JSON schema. This is critical for maintaining consistency in data-heavy tasks like grading rubrics or event logging.

#### #### Key Features

* **Built-in Tool Compatibility**: Unlike previous versions, Gemini 3 can combine Structured Outputs with tools like **Google Search**, **Code Execution**, and **Function Calling**.
* **Schema Enforcement**: By providing a JSON schema, the agent ensures that outputs follow a strict format, which is essential for audit trails or feeding data into databases (e.g., JSONB columns).

#### #### Implementation Strategy

To use this, define a `response_json_schema` in the `generation_config` and set the `response_mime_type` to `application/json`.

#### #### Python Example (Schema-based)

```python
from pydantic import BaseModel, Field
from typing import List

class GradingAnalysis(BaseModel):
    score: int = Field(description="Score from 0 to 100")
    reasoning: str = Field(description="Explanation for the score based on the image")
    criteria_met: List[str] = Field(description="List of rubric items satisfied")

# API Configuration
config = {
    "response_mime_type": "application/json",
    "response_json_schema": GradingAnalysis.model_json_schema(),
    "thinking_config": {"thinking_level": "high"}
}

response = client.models.generate_content(
    model="gemini-3-pro-preview",
    contents=["Evaluate this student's handwritten math proof.", image_part],
    config=config
)

```

#### #### Best Practices for the Agent

* **Prompt Conciseness**: When using Structured Outputs, avoid verbose prompt engineering. The schema itself acts as a constraint; just provide direct, clear instructions on *how* to fill the schema.
* **Error Handling**: Always validate the returned JSON string against your schema on the client side, as the "Preview" models may occasionally encounter edge cases.
* **Combination with Search**: If analyzing an image of a product or place, you can instruct the agent to use Google Search to verify details and then output the final verified facts in your structured JSON format.

---

Would you like me to draft a specific JSON schema for your FAIR project's rubric management?
