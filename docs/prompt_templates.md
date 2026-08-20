# Prompt Templates

## Prompt A: Destination Page Analysis

- Inputs: destination URL/title/content, anchor text
- Output: primary topic, intent, entities, related concepts, contexts, anchor meaning
- Hard requirement: return strict JSON only

## Prompt B: Blog Relevance Analysis

- Inputs: destination summary, blog title/content, anchor text
- Output: relevance score 0-100, recommendation boolean, reason, evidence spans
- Hard requirement: conservative recommendation

## Prompt C: Anchor Placement Analysis

- Inputs: destination summary, anchor text, numbered blog paragraphs, exact occurrences from deterministic code
- Output: existing anchor usage or light edit recommendation with paragraph/sentence index
- Hard requirement: never claim exact anchor beyond deterministic evidence

## Prompt D: Final Recommendation

- Inputs: deterministic signals + relevance + placement
- Output: final strict JSON object
- Hard requirement: if existing_link_found=true then linking_recommended=false
