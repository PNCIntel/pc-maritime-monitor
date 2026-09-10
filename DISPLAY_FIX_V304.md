# v3.0.4 — Connected Coverage Display Fix

Fixed the user-facing connected-coverage renderer in P&C Intelligence.

Changes:
- Literal `\n` sequences are removed before rendering.
- Internal relationship enums such as `REGIONAL_SECURITY_EXPOSURE` are translated to normal English.
- Associated ports/assets now render as name + type, followed by a small relationship caption and canonical context.
- Associated companies use the same clean presentation.
- Related-system tables also humanize relationship labels.
- Source Excel values are unchanged. This is a presentation-layer fix only.
- P&C Intelligence and P&C Trade remain separate product interfaces.
