# Common Field Specs
  * Any element that is indicated as a boolean value can only be set to values of "true" or "false" with no quotes.

  * Any element that is indicated as an integer value can only be set to integer values >= 0.

  * An element named `ssl-verify` is a common optional boolean element that may appear as a child element for other elements at any
    level. Described as "True by default. Set to False to turn off SSL certificate validation."  Omitting the "ssl-verify" element defaults
    to enabling SSL verification.

  * An identifier considered a `purpose` can be used for some YAML elements.  It is a word with only alphanumeric characters that does not exceed 10 characters.
    The purpose is used to reference the YAML element where the purpose is applied.

  * An element named `proxies` is a common optional element name.
    * The proxies element must have at least one of the following two optional elements at the next level:
      * http
      * https
    * Each of the elements under `proxies` is assigned a URL for a proxy server.
  
