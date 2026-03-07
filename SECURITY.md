# Security Policy

## Reporting a Vulnerability

We take the security of the MCP Server charm seriously. If you believe you have found a security vulnerability, please report it to us responsibly.

### How to Report

**Please do NOT report security vulnerabilities through public GitHub issues.**

Instead, please report them using GitHub's Security Advisory feature:

1. Navigate to the repository on GitHub
2. Click on the "Security" tab
3. Click "Report a vulnerability"
4. Fill out the form with details about the vulnerability

### What to Include

Please include the following information in your report:

- Type of vulnerability (e.g., authentication bypass, privilege escalation, etc.)
- Full paths of source file(s) related to the manifestation of the issue
- The location of the affected source code (tag/branch/commit or direct URL)
- Any special configuration required to reproduce the issue
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the issue, including how an attacker might exploit it

### What to Expect

- You will receive an acknowledgment of your report within 48 hours
- We will send a more detailed response within 7 days indicating the next steps
- We will keep you informed about the progress toward a fix and announcement
- We may ask for additional information or guidance

### Disclosure Policy

- Security issues are typically disclosed once a fix is available
- We follow coordinated disclosure practices
- Credit will be given to researchers who report vulnerabilities responsibly

## Supported Versions

Security updates are provided for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| latest (main) | :white_check_mark: |
| < 1.0   | :x:                |

## Security Best Practices

When deploying and using this charm:

1. **Always use the latest version** of the charm from the stable channel
2. **Use ingress with TLS** to encrypt traffic to the MCP Server
3. **Regularly backup your data**
4. **Restrict network access** to the MCP Server using network policies
6. **Review audit logs** regularly for suspicious activity
7. **Keep Juju up to date** with security patches

## Known Security Considerations

- **Exec handlers run commands on the machine.** By default, any command
  declared by a principal charm is permitted. Use the `command-allowlist`
  configuration option to restrict which executables the MCP server is allowed
  to invoke.

- **Template substitution uses argv boundaries (no shell injection), but values
  are not escaped for the target command's syntax.** For example, a user-supplied
  value that contains valid SQL will be passed verbatim to `psql`. Principal
  charms should validate or sanitise inputs in their `input_schema` where
  possible.

- **The MCP server listens on all interfaces by default.** Use firewall rules,
  Juju network spaces, or an ingress/reverse-proxy relation to restrict which
  networks can reach the server port.

- **Bearer tokens are sent in plaintext without TLS.** Always terminate TLS in
  production, either via the `certificates` relation or a TLS-terminating
  reverse proxy, to prevent credentials from being intercepted on the wire.

- **OAuth tokens must be validated against the IdP.** Clock skew between the MCP
  server and the identity provider can cause false rejections of otherwise valid
  tokens. Ensure NTP is configured on all machines.

- **Rate limiting is per-server, not per-client.** A single client can consume
  the entire quota configured via the `rate-limit` option, effectively denying
  service to other clients.

- **The subordinate charm has full machine access.** It runs handlers as root by
  default. Use the `user` field on `ExecHandler` to drop privileges, and
  restrict the `command-allowlist` to the minimum set of commands required.

## Additional Resources

- [Juju Security Documentation](https://juju.is/docs/juju/security)
