# CxOne Flow

If you are familiar with [CxFlow](https://github.com/checkmarx-ltd/cx-flow) for Checkmarx SAST, the role of CxOne Flow will be familiar.  

If not, CxOne Flow is a scan orchestrator that executes multiple source code analysis scans.  

## CxOneFlow vs CxFlow

CxOneFlow is not intended to ever reach feature parity with CxFlow.  Many CxFlow features will not apply to Checkmarx One scanning.  CxOneFlow currently orchestrates scans via webhook events for push and pull-requests involving protected branches.  CxOneFlow
itself does not create results in feedback applications.

# Quickstart and Documentation

Please refer to the [Releases](https://github.com/checkmarx-ts/cxone-flow/releases) where you will find a PDF manual that will explain configuration steps for a quick evaluation.

# Execution Features

* Supported SCMs
    * BitBucket Data Center
    * Azure DevOps Enterprise
* Scans are invoked by Push events when code is pushed to protected branches.
* Scans are invoked on Pull-Requests that target a protected branch.
* Scan results for Pull-Request scans are summarized in a pull-request comment.
* Pull-Request state is reflected in scan tags as the pull request is under
review.

