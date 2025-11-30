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
