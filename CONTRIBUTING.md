# Contributing

margi is an early, one-person project. Its scope and design still change often, so I'm not
looking for contributions right now, and I may not get to issues or pull requests quickly.

If you still want to contribute, this is how.

## Issues

Bug reports are always welcome. Please include:

- your margi version (`uv run margi --version`) and operating system,
- what you ran, what you expected and what happened instead,
- the full error message, if there is one.

Please don't put thesis text you want to keep private in an issue.

## Pull requests

**Open an issue first** and wait until we have agreed on the change. I will probably close pull
requests that arrive without a discussion, however good they are, because I can't yet commit to
reviewing or maintaining code I didn't plan for. Typo and documentation fixes can skip this step.

Once we have agreed:

1. Branch off `develop` and open the pull request against `develop`. `main` only receives
   releases.
2. Keep it to one change. Add or update tests for what you change.
3. Run the tests before you push:

   ```sh
   uv sync && uv run pytest
   ```

4. Explain in the pull request what changed and why, and link the issue.

Changes to the separation between your text and margi's (the commit guard, the CI check, the
agent permissions and the rule that AI-written text stays inside `margi/`) get the strictest
review. margi is only useful if that guarantee holds.

## AI-assisted code

You may use AI tools to write code for margi. You are responsible for every line you submit:
read it, understand it and be ready to explain it.

## License

By contributing, you agree that your contribution is licensed under the [MIT License](LICENSE).
