# Development Guidelines

## Environment
- Use conda environment: `apple-tv`
- Run Python scripts with: `conda run -n apple-tv python script.py`

## Error Notifications
Email notifications are sent when device errors occur. Configure in `.env`:
- `NOTIFY_EMAIL_FROM`: Gmail address to send from
- `NOTIFY_EMAIL_PASSWORD`: Gmail app password (get from https://myaccount.google.com/apppasswords)
- `NOTIFY_EMAIL_TO`: Recipient email (defaults to ted.foss.spamfree@gmail.com)

## Git Practices
- Commit changes frequently with clear, descriptive commit messages
- Stage and commit after completing each logical unit of work

## Code Quality
- Add clear comments explaining non-obvious logic

## Testing
- Write testable code with clear inputs/outputs and minimal side effects
- Generate unit tests for new functionality
- Ensure tests cover edge cases
