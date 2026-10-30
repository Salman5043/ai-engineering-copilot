# v14.9.2 Source Verification Against Uploaded app(1).zip

## Scope
Parsed the uploaded Python source with Python AST and compared named call expressions in the 20 specified caller functions to the expected targets. Compared analyzer call-site lines in enhanced evidence against actual call-expression lines. This is a *source-expression check*, not independent proof of import binding, runtime execution, or every statement in the 40 answers.

## Results
- 15/15 positive cases contain a matching named call expression.
- 5/5 negative cases contain no matching direct named call expression in the specified caller. This does not prove runtime impossibility.
- 13/15 positive analyzer call-site lines match the uploaded source.
- **002**: analyzer line 46, source line **100**.
- **004**: analyzer line 54, source line **117**.
- **007**: analyzer line **200** and source line **200** match.

## Interpretation
The uploaded source and architecture report disagree on two call-site locations. Do not score those two enhanced answers as line-accurate based on the stale analyzer record. Rebuild the report from the exact revision and rerun the evaluation if evaluating line grounding.

## Next checks
1. Verify import resolution for cross-file calls and constructor target identity.
2. Review 40 answers claim-by-claim against source, including any broad claims such as all exit paths, no other calls, or exact source spans.
3. Repeat LLM runs for statistically more stable baseline/enhanced comparisons.
4. Keep production retriever unchanged.
