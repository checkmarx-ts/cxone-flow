# Engine Options

Each section contains a description of the known options available for each requested scan engine. Engines
that would not make sense for use with a static configuration and unreleased engines will not
are omitted from this file.

Engines that were unknown at the time this file was compiled into a skill can be considered unreleased
for the purposes of this skill.

Explicit examples of engine configuration that are not explained in this file should be considered valid.

Each engine configuration may have a section of recommendations on the usage of an option from
Checkmarx Professional Services.

## Engine: `sast`
- `presetName` — SAST query preset to run. Example values: "Checkmarx Default", "ASA Premium"
- `incremental` — scan only changed code instead of the full codebase. "true" / "false"
- `incrementalChangeThreshold` — percent of change above which an incremental scan
  reverts to full. Example: "10"
- `incrementalInBranch` — apply incremental behavior within a branch. "true" / "false"
- `lightQueries` — run simplified queries focused on the most exploitable issues
  rather than the full standard query set. "true" / "false"
- `baseBranch` — branch used as the incremental/comparison baseline. Example: "main"
- `languageMode` — "multi" (all detected languages) or primary-language only.
  Ignored while fastScanMode is on, which forces primary.
- `filter` — include/exclude file globs, comma separated. Example: "*.java,*.js"
  or "!*.java,!*.cpp"
- `engineVerbose` — verbose engine logging. "true" / "false"
- `fastScanMode` — reduced-depth scan tuned for speed. "true" / "false"
- `recommendedExclusions` — apply Checkmarx's recommended file exclusions.
  "true" / "false"

### Professional Services Usage Recommendations

The `recommendedExclusions` option will tend to over-exclude such that large portions of valid source files
are completely excluded from the scan.  It is recommended to turn this off using the tenant global
configuration and disallow override.

Using `incremental` scans is a tradeoff of accuracy in favor of a speedy scan.  Deployment decisions and risk
assessment should never consider an incremental scan.

## Engine: `sca`

- `filter` — include/exclude file globs. Example: "!*.cpp"
- `exploitablePath` — determine whether a vulnerable package is reachable from your
  code. Requires SAST results. "true" / "false"
- `lastSastScanTime` — max age in days of a prior SAST scan reusable for Exploitable
  Path; a new SAST scan is triggered if none is that recent. Default: "1"
- `vulnerabilityComparisonMode` — baseline for deciding what counts as a New finding.
  "Project-Wide" (default, any branch) or "Branch-Based" (same branch only)
- `javaLanguageVersion` — Java version for Gradle dependency resolution; does not
  affect Maven. Documented: "8", "11", "17", "21" (default 21). Config-as-code
  example shows "25"
- `pythonLanguageVersion` — Python version for dependency resolution.
  "2.7", "3.11", "3.12", "3.13"
- `enableContainersScan` — legacy SCA-driven container scanning. Set "false" when
  running the separate Container Security scanner alongside SCA

## Engine: `kics` (IaC Security)

- `platforms` — IaC platforms to scan, comma separated.
  Example: "Ansible,CloudFormation,Dockerfile"
- `filter` — include/exclude file globs
- `presetId` — UUID of the IaC query preset

## Engine: `containers` (Container Security)

- `imagesFilter` — include/exclude discovered images. Example: "!:*latest"
- `filesFilter` — include/exclude files searched for image references.
  Examples: "*.yaml,*.yml" / "!node_modules,!dist,!build"
- `packagesFilter` — include/exclude packages in results. Example: "^internal-.*"
- `nonFinalStagesFilter` — include images from non-final Dockerfile build stages.
  "true" / "false"

## Engine: `apisec` (API Security)

- `swaggerFilter` — file globs for locating API specs
- `uuid` — reference to the Swagger/OpenAPI definition to use

## Engine: `aisc` (AI Supply Chain Security)
- `filter` — file globs.
  Example: "*.java,*.js,*.ts,package.json,package-lock.json"