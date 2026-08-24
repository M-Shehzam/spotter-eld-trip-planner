# End to end checks

Twenty-eight checks that drive the deployed app in a real browser. They run
against the hosted URLs, not a local server, because the assessment is graded
on the hosted version and a passing local run says nothing about it.

```bash
cd e2e
npm run setup    # installs Playwright and downloads Chromium, once
npm test
```

The two URLs are constants at the top of `live-suite.js`. Point them at
localhost to check a branch before deploying.

Playwright is pinned to 1.61.1. Later releases ship no Chromium build for
macOS 13, and `playwright install` answers `Playwright does not support
chromium on mac13`. On a newer machine the pin can go.

## What it covers

| Area | Checks |
| --- | --- |
| Loading | Empty state renders, page served over HTTPS |
| Cross-origin | Autocomplete reaches the API from the Vercel origin |
| Validation | An empty submit marks all three location fields |
| Keyboard | The first Tab lands on a visible skip link |
| Planning | Map, route line, and a tab per calendar day |
| Correctness | Every sheet accounts for 24 hours, sheet mileage matches route distance, the audit reports the plan compliant, the speed factor is the corrected 1.0 |
| Sharing | A plan gets a URL, and reopening it restores both the results and the form |
| Sheets | Switching tabs draws a different day, PNG export produces a real file |
| Print | Every day reaches paper, the map does not |
| Responsive | No horizontal page scroll at 390, 768, 1024 and 1600 |
| Accessibility | axe reports no serious or critical WCAG 2.1 AA violations |
| Motion | The duty line is fully drawn under `prefers-reduced-motion` |
| Failure | A 503 shows one alert naming a recovery path, and offers a retry |

## Why these exist

Every user-facing bug in this project was found by looking at a rendered page,
not by a unit test. The backend suite is thorough and stayed green while the
form silently refused to validate, while a shared link restored a plan next to
an empty form, and while the word "Midnight" was cut in half by the edge of
the grid. These checks are the answer to that.
