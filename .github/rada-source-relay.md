# Hosted Rada data refresh

The scheduled job runs on a GitHub-hosted Ubuntu runner. It opens a local SSH
forward through a Kyiv host to `data.rada.gov.ua:443`. curl keeps the original
HTTPS URL and verifies the Rada server's certificate. The Kyiv host needs no
GitHub credentials or dashboard checkout.

## Provision the relay

Use a Kyiv host with OpenSSH on port 22. From the actual host, verify HEAD and
a nonempty ranged GET for these four official paths before configuring GitHub.

- `https://data.rada.gov.ua/ogd/zal/ppz/skl9/plenary_vote_results-skl9.tsv`
- `https://data.rada.gov.ua/ogd/zal/ppz/skl9/plenary_event_question-skl9.csv`
- `https://data.rada.gov.ua/ogd/zal/ppz/skl9/plenary_deputies-skl9.csv`
- `https://data.rada.gov.ua/ogd/zal/mps/mps-trans_fr.csv`

Create a dedicated `rada-relay` account and a new Ed25519 key for Actions.
In the account's `authorized_keys`, prepend these options to the public key.

```text
restrict,port-forwarding,permitopen="data.rada.gov.ua:443"
```

Apply these settings for the account in the server's sshd configuration. Validate
the configuration with `sshd -t` before reloading it.

```text
Match User rada-relay
    AuthenticationMethods publickey
    PasswordAuthentication no
    AllowTcpForwarding local
    AllowStreamLocalForwarding no
    PermitOpen data.rada.gov.ua:443
    GatewayPorts no
    PermitTunnel no
    MaxSessions 0
Match all
```

Set the following in the repository's Actions settings.

- `RADA_RELAY_HOST` variable holds the server's public IPv4 address or DNS name.
- `RADA_RELAY_HOST_KEY` variable holds a complete `known_hosts` line for that host.
  Verify the host key against the provider console or the server's host public key.
- `RADA_RELAY_SSH_KEY` secret holds the dedicated Actions private key.

Dispatch **Update faction data** on the test branch first. Use a checkout with
stale artifacts for a full rebuild. Once that succeeds, merge the workflow to
`main` and dispatch it again. Verify the scheduled run and the published data
before disabling the Windows fallback.
