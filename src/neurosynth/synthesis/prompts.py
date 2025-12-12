"""Prompts for neurosurgical content synthesis."""

SECTION_ENHANCEMENT_PROMPT = """Enhance this section with additional detail and depth.

Current content:
{content}

Additional context to incorporate:
{context}

Requirements:
- Expand on key points
- Add supporting details
- Maintain academic tone
- Keep citations
- Ensure medical accuracy

Write the enhanced section:"""

SUBSECTION_GENERATION_PROMPT = """Analyze this section and suggest logical subsections.

Section: {title}
Content:
{content}

Return a JSON array of subsection titles (max {max_subsections}).
Each subsection should cover a distinct aspect.

Return ONLY a JSON array of strings."""

# Tone-specific section synthesis prompts
SECTION_SYNTHESIS_DESCRIPTIVE = """You are writing a section for a neurosurgical textbook chapter.

Section: {section_title}
Description: {section_description}
Word Target: approximately {word_target} words

Source Material:
{source_content}

WRITING STYLE:
Write in a descriptive, academic voice suitable for medical literature.
- Use third person and passive voice where appropriate
- Example: "The incidence of this condition is approximately..."
- Example: "Studies have demonstrated that..."
- Maintain scholarly tone with proper citation integration
- Be thorough but avoid redundancy

Requirements:
- Synthesize the source material into coherent prose
- Integrate citations naturally (use the format provided in sources)
- Present evidence objectively
- Acknowledge conflicting evidence where present
- Ensure medical accuracy
- Do not fabricate information not present in sources

FIGURE INTEGRATION:
The source material includes available figures with IDs (e.g., [FIGURE_ID: 1234]).
You MUST integrate these figures into your text where relevant by inserting the tag [FIGURE: 1234].
- Place the tag at the end of the sentence referencing the figure.
- Use at least 1 figure for every 300 words if available.
- Do not invent figure IDs. Only use those provided in the source material.

Write the section:"""

SECTION_SYNTHESIS_IMPERATIVE = """You are writing a surgical technique section for a neurosurgical operative atlas.

Section: {section_title}
Description: {section_description}
Word Target: approximately {word_target} words

Source Material:
{source_content}

WRITING STYLE:
Write in an imperative, active voice suitable for surgical instruction.
- Use direct commands: "Position the patient...", "Make the incision..."
- Example: "Identify the superficial temporal artery and protect it during dissection."
- Example: "Elevate the bone flap carefully, avoiding dural tearing."
- Be specific and actionable
- This section should read like a surgical manual

Requirements:
- Present steps in logical operative sequence
- Include specific measurements, angles, and landmarks where provided
- Emphasize key decision points and safety considerations
- Include tips for avoiding complications
- Use sources to support technique recommendations
- Do not fabricate steps not supported by source material

FIGURE INTEGRATION:
The source material includes available figures with IDs (e.g., [FIGURE_ID: 1234]).
You MUST integrate these figures into your text where relevant by inserting the tag [FIGURE: 1234].
- Place the tag at the end of the sentence referencing the figure.
- Use at least 1 figure for every 300 words if available.
- Do not invent figure IDs. Only use those provided in the source material.

"WHY" INTEGRATION:
For each major step, you MUST include the rationale at three levels if supported by the source material:
1. Anatomical Why (e.g., "We angle 15° medially because the pedicle axis deviates...")
2. Safety Why (e.g., "This keeps us 3mm from the vertebral artery...")
3. Outcome Why (e.g., "Medial angulation increases pullout strength by 40%...")

IMAGE SETS:
You MUST indicate where images should be placed using the following placeholder format:
[IMAGE: <Type> - <Description>]
Types: Overview, Detail, Schematic, 3D Model, Intraop, Danger Zone
Example: [IMAGE: Schematic - Angle measurements overlaid on the pedicle view]
Include at least one image placeholder for every major step.

Write the section:"""

# Category-enforced section synthesis prompt
CATEGORY_AWARE_SECTION_PROMPT = """You are writing a section for a neurosurgical textbook chapter.

Section: {section_title}
Description: {section_description}
Word Target: approximately {word_target} words

CONTENT RESTRICTIONS:
This section should ONLY use content from the {allowed_categories} category.
{restriction_note}

{tone_instruction}

Source Material (from {source_category} sources only):
{source_content}

Requirements:
- Synthesize the source material into coherent prose
- Stay within the topical bounds of this section
- Integrate citations naturally
- Ensure medical accuracy
- Do not include content from other categories
- Do not fabricate information not present in sources

FIGURE INTEGRATION:
The source material includes available figures with IDs (e.g., [FIGURE_ID: 1234]).
You MUST integrate these figures into your text where relevant by inserting the tag [FIGURE: 1234].
- Place the tag at the end of the sentence referencing the figure.
- Use at least 1 figure for every 300 words if available.
- Do not invent figure IDs. Only use those provided in the source material.

Write the section:"""


# =============================================================================
# 2-PASS SYNTHESIS PROMPTS (Priority 5: LLM Citation Loop)
# =============================================================================

PASS1_SYNTHESIS_PROMPT = """You are writing a section for a neurosurgical textbook chapter.

Section: {section_title}
Description: {section_description}
Word Target: approximately {word_target} words

Source Material:
{source_content}

WRITING STYLE:
{tone_instruction}

Requirements:
- Synthesize the source material into coherent prose
- Integrate citations naturally using the format provided in sources
- Present evidence objectively
- Ensure medical accuracy
- Do not fabricate information not present in sources

FIGURE REQUESTS (2-Pass Mode - Pass 1):
As you write, identify WHERE you need visual support. Instead of citing specific figures,
insert FIGURE REQUEST placeholders describing what image would best support the text:

Format: [REQUEST_FIGURE: type="<type>" topic="<description>"]

Types: surgical, anatomy, imaging, diagram, illustration
Examples:
- [REQUEST_FIGURE: type="surgical" topic="pterional craniotomy incision and exposure"]
- [REQUEST_FIGURE: type="anatomy" topic="middle cerebral artery bifurcation"]
- [REQUEST_FIGURE: type="imaging" topic="preoperative MRI showing tumor location"]

Rules:
- Insert at least 1 request for every 300 words
- Be specific in your topic description (include anatomical structures, techniques, etc.)
- Place requests at natural figure placement points (after describing a structure or step)
- Do NOT invent figure IDs - only use REQUEST_FIGURE placeholders

Write the section with figure requests:"""


PASS2_SYNTHESIS_PROMPT = """You are refining a neurosurgical textbook section with resolved figures.

Section: {section_title}

ORIGINAL DRAFT (from Pass 1):
{pass1_content}

RESOLVED FIGURES:
The following figures have been matched to your requests:
{resolved_figures}

YOUR TASK:
1. Review the resolved figures and their captions
2. Replace [REQUEST_FIGURE: ...] placeholders with actual [FIGURE: id] citations
3. If a resolved figure doesn't match well, you may omit it
4. Refine the surrounding text to naturally reference the figures
5. Ensure figure citations flow naturally in the prose

FIGURE CITATION FORMAT:
- Use [FIGURE: <id>] to cite a figure
- Place the tag at the end of the sentence that references the figure
- Reference the figure content naturally (e.g., "as shown in Figure X" or "demonstrates...")

Write the refined section with resolved figure citations:"""


PASS1_IMPERATIVE_PROMPT = """You are writing a surgical technique section for a neurosurgical operative atlas.

Section: {section_title}
Description: {section_description}
Word Target: approximately {word_target} words

Source Material:
{source_content}

WRITING STYLE:
Write in an imperative, active voice suitable for surgical instruction.
- Use direct commands: "Position the patient...", "Make the incision..."
- Be specific and actionable
- This section should read like a surgical manual

Requirements:
- Present steps in logical operative sequence
- Include specific measurements, angles, and landmarks
- Emphasize key decision points and safety considerations
- Include tips for avoiding complications

FIGURE REQUESTS (2-Pass Mode - Pass 1):
For each major step, insert FIGURE REQUEST placeholders:

Format: [REQUEST_FIGURE: type="<type>" topic="<description>"]

Types: surgical, anatomy, imaging, diagram, intraop
Examples:
- [REQUEST_FIGURE: type="surgical" topic="patient positioning for pterional approach"]
- [REQUEST_FIGURE: type="intraop" topic="bone flap elevation showing dural exposure"]
- [REQUEST_FIGURE: type="diagram" topic="pedicle screw trajectory angles"]

Rules:
- At least 1 figure request per major surgical step
- Be specific about what the image should demonstrate
- Include relevant anatomical landmarks in descriptions
- Do NOT use actual figure IDs in Pass 1

"WHY" INTEGRATION:
For each major step, include the rationale:
1. Anatomical Why (e.g., "We angle 15° medially because...")
2. Safety Why (e.g., "This keeps us 3mm from...")
3. Outcome Why (e.g., "Medial angulation increases pullout strength...")

Write the section with figure requests:"""
