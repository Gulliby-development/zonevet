<p align="center"><img src="docs/logo.svg" width="96" alt="" /></p>

# zonevet

zonevet is an offline command-line tool for people who edit DNS master-format zone files by hand. It checks zone syntax and common configuration mistakes, prints records in canonical form, and compares two zone versions. It does not resolve names or access the network.

[![CI](https://github.com/Gulliby-development/zonevet/actions/workflows/ci.yml/badge.svg)](https://github.com/Gulliby-development/zonevet/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Install

From the repository root, install with:

```text
pip install .
```

Zonevet needs Python 3.11 or newer and has no dependencies. Run the module with `python -m zonevet ARGS`, replacing `ARGS` with a command and its arguments.

## Usage

`check` validates one or more zone files, `list` prints a zone's records, and `diff` compares two zone files. Use `-` for standard input. The command synopsis is:

```text
usage: zonevet check [--origin NAME] ZONE...
       zonevet list [--origin NAME] [--type TYPE] ZONE
       zonevet diff [--origin NAME] OLD NEW
```

## Zone files

Zonevet reads UTF-8 master-format zone files. It supports origins, TTL directives, comments, quoted strings, and multiline parenthesized records. The examples below are the supplied worked examples.

`good.zone`:

```zone
$ORIGIN example.com.
$TTL 1h
@       IN SOA ns1 hostmaster (
            2024010101 ; serial
            2h         ; refresh
            15m        ; retry
            2w         ; expire
            1h )       ; minimum
        IN NS   ns1
        IN NS   ns2.example.net.
        IN MX   10 mail
        IN TXT  "v=spf1 mx -all" "say \"hi\""
ns1     IN A    192.0.2.53
mail    A       192.0.2.25
www     300 IN  CNAME web
web     IN AAAA 2001:0db8:0000:0000:0000:0000:0000:0001
web     A       192.0.2.80
_sip._tcp SRV 10 60 5060 mail
```

`bad.zone`:

```zone
$ORIGIN example.com.
$TTL 300
www     CNAME   web
www     A       192.0.2.1
web     CNAME   www
@       MX      10 www
mail    A       192.0.2.25
mail    A       192.0.2.25
ns1     600 A   192.0.2.53
ns1     A       192.0.2.54
sub     NS      ns2
alias   CNAME   www.example.com
other.org. A    192.0.2.9
@       SOA     ns1 admin 1 600 900 1000 300
```

## Checks

The checks catch missing or misplaced SOA and NS records, duplicate records, CNAME conflicts and loops, alias targets, missing address records, inconsistent RRset TTLs, records outside the zone, invalid SOA timing, likely missing trailing dots, and CNAME, NS, MX or SRV targets written as IPv4 addresses (ZC112: `IN NS 192.0.2.53` names the host `192.0.2.53.example.com.`, so use a host name with its own A record).

For `good.zone`, `zonevet check good.zone` prints:

```text
ok, 1 file checked
```

For `bad.zone`, `zonevet check bad.zone` prints:

```text
bad.zone:3: ZC103 "www.example.com." has a CNAME and other data (line 4)
bad.zone:3: ZC105 CNAME loop: www.example.com. -> web.example.com. -> www.example.com.
bad.zone:3: ZC109 no NS record at the zone apex
bad.zone:6: ZC104 MX target "www.example.com." is a CNAME (line 3)
bad.zone:8: ZC102 duplicate of line 7
bad.zone:10: ZC107 RRset "ns1.example.com." A has different TTLs (600 on line 9, 300 on line 10)
bad.zone:11: ZC106 NS target "ns2.example.com." has no A or AAAA record
bad.zone:12: ZC111 "www.example.com" is relative and ends with the zone name (missing trailing dot?)
bad.zone:13: ZC108 "other.org." is outside the zone "example.com."
bad.zone:14: ZC101 SOA is not the first record
bad.zone:14: ZC110 SOA retry (900) is not smaller than refresh (600)
bad.zone:14: ZC110 SOA expire (1000) is not larger than refresh plus retry (1500)
12 problems in 1 file, 1 file checked
```

`zonevet list good.zone` prints:

```text
example.com. 3600 IN SOA ns1.example.com. hostmaster.example.com. 2024010101 7200 900 1209600 3600
example.com. 3600 IN NS ns1.example.com.
example.com. 3600 IN NS ns2.example.net.
example.com. 3600 IN MX 10 mail.example.com.
example.com. 3600 IN TXT "v=spf1 mx -all" "say \"hi\""
ns1.example.com. 3600 IN A 192.0.2.53
mail.example.com. 3600 IN A 192.0.2.25
www.example.com. 300 IN CNAME web.example.com.
web.example.com. 3600 IN AAAA 2001:db8::1
web.example.com. 3600 IN A 192.0.2.80
_sip._tcp.example.com. 3600 IN SRV 10 60 5060 mail.example.com.
```

`zonevet list --type a good.zone` prints:

```text
ns1.example.com. 3600 IN A 192.0.2.53
mail.example.com. 3600 IN A 192.0.2.25
web.example.com. 3600 IN A 192.0.2.80
```

For the diff example, `new.zone` is `good.zone` with serial `2024010102`, the `web` A address changed to `192.0.2.81`, `www` TTL changed to `600`, the `mail` A record removed, and `blog A 192.0.2.90` added. `zonevet diff good.zone new.zone` prints:

```text
+ blog.example.com. 3600 IN A 192.0.2.90
- mail.example.com. 3600 IN A 192.0.2.25
- web.example.com. 3600 IN A 192.0.2.80
+ web.example.com. 3600 IN A 192.0.2.81
~ www.example.com. CNAME web.example.com.: ttl 300 -> 600
serial 2024010101 -> 2024010102
5 changes
```

The reverse command, `zonevet diff new.zone good.zone`, ends with:

```text
serial 2024010102 -> 2024010101
5 changes
warning: the SOA serial did not increase (2024010101)
```

## Exit codes

Exit code 0 means the command completed without a reported problem. Exit code 1 reports check findings, a list/diff syntax error, or a diff with changes. Exit code 2 reports a usage or input error.

## Development

Install the development tools with `python -m pip install pytest ruff`, then run the test suite and linter from the repository root:


```text
pytest -q
ruff check .
```

## License

MIT, see [LICENSE](LICENSE).

---

Built with BAKED
