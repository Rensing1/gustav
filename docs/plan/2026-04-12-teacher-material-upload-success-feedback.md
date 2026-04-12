## Teacher material upload success feedback

### User story
- As a teacher, when I upload a material in the node editor, I want to immediately see that it worked so I do not assume the upload failed.

### BDD
- Given a successful file-material upload, when the create action returns, then the new material is visible immediately without a manual page reload.
- Given a successful markdown-material create, when the create action returns, then the new material is visible immediately without a manual page reload.
- Given a successful material create, when the editor updates, then a visible success message is shown in the node editor.
- Given the follow-up editor read is stale, when the backend create/finalize already returned the created material, then the UI still contains that material exactly once.

### Implementation intent
- Use the material returned by the create/finalize response as the immediate source of truth.
- Keep the existing editor reread as a best-effort refresh, but merge the created material into the returned editor state if the reread is still stale.
- Render an inline success status in the node editor so successful creates have explicit user feedback.

### Verification
- Server action tests cover stale reread merge for file and markdown materials.
- Page interaction tests cover visible success feedback and immediate material rendering from a success form payload.
