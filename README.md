# CxOne Flow

If you are familiar with [CxFlow](https://github.com/checkmarx-ltd/cx-flow) for Checkmarx SAST, you will be familiar with the role of CxOneFlow.  

For those that have not used CxFlow with Checkmarx SAST, CxOneFlow is a scan orchestrator that executes multiple source code analysis scans.  It is driven by web hook events coming from a source control system.

## CxOneFlow vs CxFlow

CxOneFlow is not intended to ever reach feature parity with CxFlow.  Many CxFlow features will not apply to Checkmarx One scanning.  CxOneFlow currently orchestrates scans via webhook events for push and pull-requests involving protected branches.  CxOneFlow
itself does not create results in feedback applications.

# Quickstart and Documentation

Please refer to the [Releases](https://github.com/checkmarx-ts/cxone-flow/releases) where you will find the following downloadable artifacts:

* A Claude skill that will answer questions about how CxOneFlow works and assist in configuration.
* A complete PDF manual that covers all topics in a human-readable, structured format.

Using Claude to guide setup and configuration will be the most rapid method of starting a working CxOneFlow server.

# Execution Features

* Supported SCMs
    * BitBucket Data Center
    * Azure DevOps Enterprise, Self-Hosted and Cloud
    * GitHub Enterprise Self-Hosted and Cloud
    * GitLab Self-Hosted and Cloud
* Scans are invoked by Push events when code is pushed to protected branches.
* Scans are invoked on Pull-Requests that target a protected branch.
* Scan results for Pull-Request scans are summarized in a pull-request comment.
* Pull-Request state is reflected in scan tags as the pull request is under review.
* Pre-scan execution of SCA Resolver and/or shell script.
