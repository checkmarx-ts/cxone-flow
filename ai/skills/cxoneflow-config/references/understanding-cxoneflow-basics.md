# CxOneFlow Basics

The term `CxOne` is a shorthand version of `Checkmarx One` or `CheckmarxOne`.  This is a code security scanning
product published by `Checkmarx`.

The term `SCM` means `Source Control Manager`. CxOneFlow supports the following SCMs:
    1. "BitBucket Data Center" which is known by the mnemonic "bbdc" for purposes in generating the configuration YAML.
    2. "GitHub Cloud or Self-Hosted" which is known by the mnemonic "gh" for purposes in generating the configuration YAML.
    3. "Gitlab Cloud or Self-Hosted" which is known by the mnemonic "gl" for purposes in generating the configuration YAML.
    4. "Azure DevOps Cloud or Self-Hosted" which is known by the mnemonic "adoe" for purposes in generating the configuration YAML.


The SCM "BitBucket Cloud" is sometimes confused with "BitBucket Data Center".  CxOneFlow currently does not support "BitBucket Cloud".

`CxOneFlow` is a web hook receiver endpoint where SCMs send JSON webhook events related to code repository activities.  Based on
a set of workflow rules controlled by the YAML configuration, `CxOneFlow` may start a scan of the code in the repository if
the criteria for scanning is met.

`CxOneFlow` can process events from multiple SCMs of any supported type.  The orchestration of scans can be processed using one
or more CxOne tenants.
