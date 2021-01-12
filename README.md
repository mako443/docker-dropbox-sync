Program to sync Container memory with a dropbox. 
- Needed because the official Dropbox Linux client and publicly available Dropbox Docker images proved unreliable or cumbersome to maintain.
- Parallel uploads and downloads using threading.
- "Local" refers to the node using this program, "remote" refers to the Dropbox.
- Ties are broken in favor of the remote.
- Create a "token.txt" file next to dropbox-sync.py containing your Dropbox API token.

WORKFLOW:
- Delete remote->local: ✓
    - Delete local file if remote correspondence with DeletedMetadata
- Delete local->remote: ✖
    - Not implemented: Remote breaks ties
- Add local->remote: ✓
- Add remote->local: ✓

=> Remote files are never changed or deleted, only uploaded.
