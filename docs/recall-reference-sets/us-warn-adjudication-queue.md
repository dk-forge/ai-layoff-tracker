# US WARN reference set — adjudication sheet

Built `2026-08-13T07:29:39Z` from a measurement taken `2026-08-13T06:50:31Z`. **Rebuild it before deciding** (`python3 railway/warn_adjudication_pack.py --write`) — it reads live data and live data moves.

Reference set: `us-warn-ca-tx-fl-tn-2025-07_2026-06`. Definition: [`docs/recall-reference-sets/US-WARN-REFERENCE-SET-DEFINITION.md`](../../docs/recall-reference-sets/US-WARN-REFERENCE-SET-DEFINITION.md). Nothing in this set is published to `/benchmarks/recall` and nothing in it touches the SEC Item 2.05 figure.

**132 events are pending**, carrying 714 candidate rows between them.

The arithmetics, so the range is known before the first decision. They are arithmetic, not targets, and none of them is a prediction about how the entries below should go:

- every pending candidate accepted: **99/100 = 99.0%  (Wilson 95% CI [94.6%, 99.8%], width 5.3%)**
- only the exact-tier candidates accepted: **99/100 = 99.0%  (Wilson 95% CI [94.6%, 99.8%], width 5.3%)**
- only the candidates where every fact lines up: **74/100 = 74.0%  (Wilson 95% CI [64.6%, 81.6%], width 17.0%)**
- nothing accepted (today's published figure): **0/100 = 0.0%  (Wilson 95% CI [0.0%, 3.7%], width 3.7%)**

**Every line below describes exactly ONE candidate row.** An event with three candidates has three lines, each carrying only its own flags. That is not a formatting preference: on 2026-08-12 a pooled summary line on the SEC sheet described a co-proposed row and a correct Dow row was rejected because of it.

| # | state | notice | notified | candidate row | tier | what is there to look at, for THIS ROW ONLY |
|---:|---|---|---:|---|---|---|
| 1 | CA | [Republic National Distributing Company](#1-ca-republic-national-distributing-company) 2025-07-01 | 1,364 | `137738` (event 2463) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 1 | CA | [Republic National Distributing Company](#1-ca-republic-national-distributing-company) 2025-07-01 | 1,364 | `137736` (event 2461) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 1 | CA | [Republic National Distributing Company](#1-ca-republic-national-distributing-company) 2025-07-01 | 1,364 | `137725` (event 2450) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 1 | CA | [Republic National Distributing Company](#1-ca-republic-national-distributing-company) 2025-07-01 | 1,364 | `137729` (event 2454) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Republic National Distributing Company, LLC' differs from the published 'Republic National Distributing Company' |
| 1 | CA | [Republic National Distributing Company](#1-ca-republic-national-distributing-company) 2025-07-01 | 1,364 | `137728` (event 2453) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Republic National Distributing Company (14402)' differs from the published 'Republic National Distributing Company' |
| 1 | CA | [Republic National Distributing Company](#1-ca-republic-national-distributing-company) 2025-07-01 | 1,364 | `137727` (event 2452) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Republic National Distributing Company (14352)' differs from the published 'Republic National Distributing Company' |
| 1 | CA | [Republic National Distributing Company](#1-ca-republic-national-distributing-company) 2025-07-01 | 1,364 | `70355` (event 43695) | loose | row source is news/filing, not a WARN-tier row; job_count 1756 matches neither a component row nor the notice total 1364; row date equals this notice's earliest published effective date; stored name 'Republic National' differs from the published 'Republic National Distributing Company' |
| 2 | CA | [(1045) San Diego LGBT Community Center](#2-ca-1045--san-diego-lgbt-community-center) 2025-07-03 | 6 | `137699` (event 2431) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 3 | CA | [Intel Corporation (Robert Noyce Building)](#3-ca-intel-corporation--robert-noyce-building) 2025-07-07 | 584 | `138141` (event 2657) | exact | job_count equals one published component row of this notice; row date is 8 day(s) after the notice date |
| 3 | CA | [Intel Corporation (Robert Noyce Building)](#3-ca-intel-corporation--robert-noyce-building) 2025-07-07 | 584 | `136875` (event 1965) | loose | job_count 45 matches neither a component row nor the notice total 584; row date is 146 day(s) after the notice date |
| 3 | CA | [Intel Corporation (Robert Noyce Building)](#3-ca-intel-corporation--robert-noyce-building) 2025-07-07 | 584 | `138203` (event 2699) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Intel Corporation' differs from the published 'Intel Corporation (Robert Noyce Building)' |
| 3 | CA | [Intel Corporation (Robert Noyce Building)](#3-ca-intel-corporation--robert-noyce-building) 2025-07-07 | 584 | `138162` (event 2678) | exact | job_count equals one published component row of this notice; row date is 8 day(s) after the notice date; stored name 'Intel Corporation - SC-2' differs from the published 'Intel Corporation (Robert Noyce Building)' |
| 3 | CA | [Intel Corporation (Robert Noyce Building)](#3-ca-intel-corporation--robert-noyce-building) 2025-07-07 | 584 | `138161` (event 2677) | exact | job_count equals one published component row of this notice; row date is 8 day(s) after the notice date; stored name 'Intel Corporation - SC-1 3065 Bowers' differs from the published 'Intel Corporation (Robert Noyce Building)' |
| 3 | CA | [Intel Corporation (Robert Noyce Building)](#3-ca-intel-corporation--robert-noyce-building) 2025-07-07 | 584 | `138146` (event 2662) | exact | job_count equals one published component row of this notice; row date is 8 day(s) after the notice date; stored name 'Intel Corporation (SC-12)' differs from the published 'Intel Corporation (Robert Noyce Building)' |
| 3 | CA | [Intel Corporation (Robert Noyce Building)](#3-ca-intel-corporation--robert-noyce-building) 2025-07-07 | 584 | `138145` (event 2661) | exact | job_count equals one published component row of this notice; row date is 8 day(s) after the notice date; stored name 'Intel Corporation (SC-11)' differs from the published 'Intel Corporation (Robert Noyce Building)' |
| 3 | CA | [Intel Corporation (Robert Noyce Building)](#3-ca-intel-corporation--robert-noyce-building) 2025-07-07 | 584 | `138144` (event 2660) | exact | job_count equals one published component row of this notice; row date is 8 day(s) after the notice date; stored name 'Intel Corporation (SC-9)' differs from the published 'Intel Corporation (Robert Noyce Building)' |
| 3 | CA | [Intel Corporation (Robert Noyce Building)](#3-ca-intel-corporation--robert-noyce-building) 2025-07-07 | 584 | `138143` (event 2659) | exact | job_count equals one published component row of this notice; row date is 8 day(s) after the notice date; stored name 'Intel Corporation (SC-2)' differs from the published 'Intel Corporation (Robert Noyce Building)' |
| 3 | CA | [Intel Corporation (Robert Noyce Building)](#3-ca-intel-corporation--robert-noyce-building) 2025-07-07 | 584 | `138142` (event 2658) | exact | job_count equals one published component row of this notice; row date is 8 day(s) after the notice date; stored name 'Intel Corporation (SC-1)' differs from the published 'Intel Corporation (Robert Noyce Building)' |
| 3 | CA | [Intel Corporation (Robert Noyce Building)](#3-ca-intel-corporation--robert-noyce-building) 2025-07-07 | 584 | `136878` (event 1968) | exact | job_count equals one published component row of this notice; row date is 146 day(s) after the notice date; stored name 'Intel Corporation (SC-9)' differs from the published 'Intel Corporation (Robert Noyce Building)' |
| 3 | CA | [Intel Corporation (Robert Noyce Building)](#3-ca-intel-corporation--robert-noyce-building) 2025-07-07 | 584 | `136876` (event 1966) | exact | job_count equals one published component row of this notice; row date is 146 day(s) after the notice date; stored name 'Intel Corporation (SC-1)' differs from the published 'Intel Corporation (Robert Noyce Building)' |
| 3 | CA | [Intel Corporation (Robert Noyce Building)](#3-ca-intel-corporation--robert-noyce-building) 2025-07-07 | 584 | `138207` (event 2703) | loose | job_count 54 matches neither a component row nor the notice total 584; row date equals this notice's earliest published effective date; stored name 'Intel Corporation' differs from the published 'Intel Corporation (Robert Noyce Building)' |
| 3 | CA | [Intel Corporation (Robert Noyce Building)](#3-ca-intel-corporation--robert-noyce-building) 2025-07-07 | 584 | `138205` (event 2701) | loose | job_count 83 matches neither a component row nor the notice total 584; row date equals this notice's earliest published effective date; stored name 'Intel Corporation' differs from the published 'Intel Corporation (Robert Noyce Building)' |
| 3 | CA | [Intel Corporation (Robert Noyce Building)](#3-ca-intel-corporation--robert-noyce-building) 2025-07-07 | 584 | `138204` (event 2700) | loose | job_count 170 matches neither a component row nor the notice total 584; row date equals this notice's earliest published effective date; stored name 'Intel Corporation' differs from the published 'Intel Corporation (Robert Noyce Building)' |
| 3 | CA | [Intel Corporation (Robert Noyce Building)](#3-ca-intel-corporation--robert-noyce-building) 2025-07-07 | 584 | `138165` (event 2681) | loose | job_count 45 matches neither a component row nor the notice total 584; row date is 8 day(s) after the notice date; stored name 'Intel Corporation' differs from the published 'Intel Corporation (Robert Noyce Building)' |
| 3 | CA | [Intel Corporation (Robert Noyce Building)](#3-ca-intel-corporation--robert-noyce-building) 2025-07-07 | 584 | `138164` (event 2680) | loose | job_count 2 matches neither a component row nor the notice total 584; row date is 8 day(s) after the notice date; stored name 'Intel Corporation - SC-11' differs from the published 'Intel Corporation (Robert Noyce Building)' |
| 3 | CA | [Intel Corporation (Robert Noyce Building)](#3-ca-intel-corporation--robert-noyce-building) 2025-07-07 | 584 | `138163` (event 2679) | loose | job_count 4 matches neither a component row nor the notice total 584; row date is 8 day(s) after the notice date; stored name 'Intel Corporation - SC-9' differs from the published 'Intel Corporation (Robert Noyce Building)' |
| 3 | CA | [Intel Corporation (Robert Noyce Building)](#3-ca-intel-corporation--robert-noyce-building) 2025-07-07 | 584 | `138160` (event 2676) | loose | job_count 57 matches neither a component row nor the notice total 584; row date is 8 day(s) after the notice date; stored name 'Intel Corporation - Robert Noyce' differs from the published 'Intel Corporation (Robert Noyce Building)' |
| 3 | CA | [Intel Corporation (Robert Noyce Building)](#3-ca-intel-corporation--robert-noyce-building) 2025-07-07 | 584 | `138159` (event 2675) | loose | job_count 26 matches neither a component row nor the notice total 584; row date is 8 day(s) after the notice date; stored name 'Intel Corporation - SC-12' differs from the published 'Intel Corporation (Robert Noyce Building)' |
| 3 | CA | [Intel Corporation (Robert Noyce Building)](#3-ca-intel-corporation--robert-noyce-building) 2025-07-07 | 584 | `138158` (event 2674) | loose | job_count 3 matches neither a component row nor the notice total 584; row date is 8 day(s) after the notice date; stored name 'Intel Corporation - SC-11' differs from the published 'Intel Corporation (Robert Noyce Building)' |
| 3 | CA | [Intel Corporation (Robert Noyce Building)](#3-ca-intel-corporation--robert-noyce-building) 2025-07-07 | 584 | `138157` (event 2673) | loose | job_count 2 matches neither a component row nor the notice total 584; row date is 8 day(s) after the notice date; stored name 'Intel Corporation - SC-9' differs from the published 'Intel Corporation (Robert Noyce Building)' |
| 3 | CA | [Intel Corporation (Robert Noyce Building)](#3-ca-intel-corporation--robert-noyce-building) 2025-07-07 | 584 | `138156` (event 2672) | loose | job_count 76 matches neither a component row nor the notice total 584; row date is 8 day(s) after the notice date; stored name 'Intel Corporation - Robert Noyce Building' differs from the published 'Intel Corporation (Robert Noyce Building)' |
| 3 | CA | [Intel Corporation (Robert Noyce Building)](#3-ca-intel-corporation--robert-noyce-building) 2025-07-07 | 584 | `138155` (event 2671) | loose | job_count 50 matches neither a component row nor the notice total 584; row date is 8 day(s) after the notice date; stored name 'Intel Corporation (SC-12)' differs from the published 'Intel Corporation (Robert Noyce Building)' |
| 3 | CA | [Intel Corporation (Robert Noyce Building)](#3-ca-intel-corporation--robert-noyce-building) 2025-07-07 | 584 | `138154` (event 2670) | loose | job_count 2 matches neither a component row nor the notice total 584; row date is 8 day(s) after the notice date; stored name 'Intel Corporation (SC-9)' differs from the published 'Intel Corporation (Robert Noyce Building)' |
| 3 | CA | [Intel Corporation (Robert Noyce Building)](#3-ca-intel-corporation--robert-noyce-building) 2025-07-07 | 584 | `138153` (event 2669) | loose | job_count 46 matches neither a component row nor the notice total 584; row date is 8 day(s) after the notice date; stored name 'Intel Corporation (Robert Noyce)' differs from the published 'Intel Corporation (Robert Noyce Building)' |
| 3 | CA | [Intel Corporation (Robert Noyce Building)](#3-ca-intel-corporation--robert-noyce-building) 2025-07-07 | 584 | `138152` (event 2668) | loose | job_count 55 matches neither a component row nor the notice total 584; row date is 8 day(s) after the notice date; stored name 'Intel Corporation (SC-12)' differs from the published 'Intel Corporation (Robert Noyce Building)' |
| 3 | CA | [Intel Corporation (Robert Noyce Building)](#3-ca-intel-corporation--robert-noyce-building) 2025-07-07 | 584 | `138151` (event 2667) | loose | job_count 5 matches neither a component row nor the notice total 584; row date is 8 day(s) after the notice date; stored name 'Intel Corporation (SC-11)' differs from the published 'Intel Corporation (Robert Noyce Building)' |
| 3 | CA | [Intel Corporation (Robert Noyce Building)](#3-ca-intel-corporation--robert-noyce-building) 2025-07-07 | 584 | `138150` (event 2666) | loose | job_count 16 matches neither a component row nor the notice total 584; row date is 8 day(s) after the notice date; stored name 'Intel Corporation (SC-9)' differs from the published 'Intel Corporation (Robert Noyce Building)' |
| 3 | CA | [Intel Corporation (Robert Noyce Building)](#3-ca-intel-corporation--robert-noyce-building) 2025-07-07 | 584 | `138149` (event 2665) | loose | job_count 43 matches neither a component row nor the notice total 584; row date is 8 day(s) after the notice date; stored name 'Intel Corporation (SC-2)' differs from the published 'Intel Corporation (Robert Noyce Building)' |
| 3 | CA | [Intel Corporation (Robert Noyce Building)](#3-ca-intel-corporation--robert-noyce-building) 2025-07-07 | 584 | `138148` (event 2664) | loose | job_count 4 matches neither a component row nor the notice total 584; row date is 8 day(s) after the notice date; stored name 'Intel Corporation (SC-1)' differs from the published 'Intel Corporation (Robert Noyce Building)' |
| 3 | CA | [Intel Corporation (Robert Noyce Building)](#3-ca-intel-corporation--robert-noyce-building) 2025-07-07 | 584 | `138147` (event 2663) | loose | job_count 203 matches neither a component row nor the notice total 584; row date is 8 day(s) after the notice date; stored name 'Intel Corporation (Robert Noyce)' differs from the published 'Intel Corporation (Robert Noyce Building)' |
| 3 | CA | [Intel Corporation (Robert Noyce Building)](#3-ca-intel-corporation--robert-noyce-building) 2025-07-07 | 584 | `136879` (event 1969) | loose | job_count 10 matches neither a component row nor the notice total 584; row date is 146 day(s) after the notice date; stored name 'Intel Corporation (SC-12)' differs from the published 'Intel Corporation (Robert Noyce Building)' |
| 3 | CA | [Intel Corporation (Robert Noyce Building)](#3-ca-intel-corporation--robert-noyce-building) 2025-07-07 | 584 | `136877` (event 1967) | loose | job_count 2 matches neither a component row nor the notice total 584; row date is 146 day(s) after the notice date; stored name 'Intel Corporation (SC-2)' differs from the published 'Intel Corporation (Robert Noyce Building)' |
| 4 | CA | [Quanex Homeshield LLC](#4-ca-quanex-homeshield-llc) 2025-07-11 | 15 | `137666` (event 2414) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 5 | CA | [Decra Roofing Systems, Inc.](#5-ca-decra-roofing-systems--inc) 2025-07-28 | 61 | `137465` (event 2306) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 5 | CA | [Decra Roofing Systems, Inc.](#5-ca-decra-roofing-systems--inc) 2025-07-28 | 61 | `137464` (event 2305) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 6 | CA | [Bausch Health US, LLC](#6-ca-bausch-health-us--llc) 2025-08-13 | 49 | `137919` (event 2530) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 7 | CA | [Enloe Health](#7-ca-enloe-health) 2025-08-25 | 78 | `137166` (event 2120) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 8 | CA | [Essendant](#8-ca-essendant) 2025-09-04 | 146 | `136567` (event 1794) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 8 | CA | [Essendant](#8-ca-essendant) 2025-09-04 | 146 | `177210` (event 149943) | loose | job_count 99 matches neither a component row nor the notice total 146; row date is 394 day(s) after the notice date; stored name 'Essendant Co.' differs from the published 'Essendant' |
| 8 | CA | [Essendant](#8-ca-essendant) 2025-09-04 | 146 | `177209` (event 149942) | loose | job_count 4 matches neither a component row nor the notice total 146; row date is 394 day(s) after the notice date; stored name 'Essendant Co.' differs from the published 'Essendant' |
| 9 | CA | [Dreyer's Grand Ice Cream](#9-ca-dreyer-s-grand-ice-cream) 2025-09-23 | 914 | `136937` (event 1998) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 9 | CA | [Dreyer's Grand Ice Cream](#9-ca-dreyer-s-grand-ice-cream) 2025-09-23 | 914 | `136926` (event 1989) | exact | job_count equals one published component row of this notice; row date is 62 day(s) after the notice date |
| 10 | CA | [Palo Verde Healthcare District](#10-ca-palo-verde-healthcare-district) 2025-09-24 | 94 | `136935` (event 1996) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 10 | CA | [Palo Verde Healthcare District](#10-ca-palo-verde-healthcare-district) 2025-09-24 | 94 | `136350` (event 1641) | loose | job_count 99 matches neither a component row nor the notice total 94; row date is 122 day(s) after the notice date; stored name 'Palo Verde Hospital' differs from the published 'Palo Verde Healthcare District' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136455` (event 1705) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136454` (event 1704) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136453` (event 1703) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136452` (event 1702) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135379` (event 1155) | loose | job_count 89 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135378` (event 1154) | loose | job_count 81 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135377` (event 1153) | loose | job_count 87 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135376` (event 1152) | loose | job_count 58 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135375` (event 1151) | loose | job_count 11 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135374` (event 1150) | loose | job_count 3 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135373` (event 1149) | loose | job_count 32 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135372` (event 1148) | loose | job_count 72 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136333` (event 1632) | loose | job_count 3 matches neither a component row nor the notice total 555; row date is 116 day(s) after the notice date; stored name 'Amazon (SFO38)' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136332` (event 1631) | loose | job_count 71 matches neither a component row nor the notice total 555; row date is 116 day(s) after the notice date; stored name 'Amazon (SFO28)' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136331` (event 1630) | loose | job_count 18 matches neither a component row nor the notice total 555; row date is 116 day(s) after the notice date; stored name 'Amazon (SFO19)' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136330` (event 1629) | loose | job_count 41 matches neither a component row nor the notice total 555; row date is 116 day(s) after the notice date; stored name 'Amazon (SFO13)' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136329` (event 1628) | loose | job_count 1 matches neither a component row nor the notice total 555; row date is 116 day(s) after the notice date; stored name 'Amazon (ONM213)' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136328` (event 1627) | loose | job_count 3 matches neither a component row nor the notice total 555; row date is 116 day(s) after the notice date; stored name 'Amazon (ONM212)' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136327` (event 1626) | loose | job_count 1 matches neither a component row nor the notice total 555; row date is 116 day(s) after the notice date; stored name 'Amazon (SAN 5)' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136326` (event 1625) | loose | job_count 1 matches neither a component row nor the notice total 555; row date is 116 day(s) after the notice date; stored name 'Amazon (SAN 3)' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136325` (event 1624) | loose | job_count 5 matches neither a component row nor the notice total 555; row date is 116 day(s) after the notice date; stored name 'Amazon (SAN 21)' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136324` (event 1623) | loose | job_count 3 matches neither a component row nor the notice total 555; row date is 116 day(s) after the notice date; stored name 'Amazon (SAN 18)' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136323` (event 1622) | loose | job_count 61 matches neither a component row nor the notice total 555; row date is 116 day(s) after the notice date; stored name 'Amazon (SAN 17)' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136322` (event 1621) | loose | job_count 50 matches neither a component row nor the notice total 555; row date is 116 day(s) after the notice date; stored name 'Amazon (SAN 15)' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136321` (event 1620) | loose | job_count 24 matches neither a component row nor the notice total 555; row date is 116 day(s) after the notice date; stored name 'Amazon (SAN 13)' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136320` (event 1619) | loose | job_count 45 matches neither a component row nor the notice total 555; row date is 116 day(s) after the notice date; stored name 'Amazon SNA3' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136319` (event 1618) | loose | job_count 16 matches neither a component row nor the notice total 555; row date is 116 day(s) after the notice date; stored name 'Amazon SNA19' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136318` (event 1617) | loose | job_count 1 matches neither a component row nor the notice total 555; row date is 116 day(s) after the notice date; stored name 'Amazon SNA18' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136317` (event 1616) | loose | job_count 12 matches neither a component row nor the notice total 555; row date is 116 day(s) after the notice date; stored name 'Amazon SNA17' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136316` (event 1615) | loose | job_count 64 matches neither a component row nor the notice total 555; row date is 116 day(s) after the notice date; stored name 'Amazon SNA16' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136315` (event 1614) | loose | job_count 17 matches neither a component row nor the notice total 555; row date is 116 day(s) after the notice date; stored name 'Amazon SNA12' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136314` (event 1613) | loose | job_count 178 matches neither a component row nor the notice total 555; row date is 116 day(s) after the notice date; stored name 'Amazon SNA11' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136313` (event 1612) | loose | job_count 18 matches neither a component row nor the notice total 555; row date is 116 day(s) after the notice date; stored name 'Amazon SJC44' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136312` (event 1611) | loose | job_count 50 matches neither a component row nor the notice total 555; row date is 116 day(s) after the notice date; stored name 'Amazon SJC38' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136311` (event 1610) | loose | job_count 8 matches neither a component row nor the notice total 555; row date is 116 day(s) after the notice date; stored name 'Amazon SJC25' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136310` (event 1609) | loose | job_count 2 matches neither a component row nor the notice total 555; row date is 116 day(s) after the notice date; stored name 'Amazon SFO39' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136309` (event 1608) | loose | job_count 12 matches neither a component row nor the notice total 555; row date is 116 day(s) after the notice date; stored name 'Amazon SFO36' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136308` (event 1607) | loose | job_count 75 matches neither a component row nor the notice total 555; row date is 116 day(s) after the notice date; stored name 'Amazon SFO24' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136307` (event 1606) | loose | job_count 69 matches neither a component row nor the notice total 555; row date is 116 day(s) after the notice date; stored name 'Amazon SFO22' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136306` (event 1605) | loose | job_count 18 matches neither a component row nor the notice total 555; row date is 116 day(s) after the notice date; stored name 'Amazon SFO12' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136305` (event 1604) | loose | job_count 85 matches neither a component row nor the notice total 555; row date is 116 day(s) after the notice date; stored name 'Amazon (SJC32)' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136304` (event 1603) | loose | job_count 27 matches neither a component row nor the notice total 555; row date is 116 day(s) after the notice date; stored name 'Amazon (SJC31)' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136303` (event 1602) | loose | job_count 80 matches neither a component row nor the notice total 555; row date is 116 day(s) after the notice date; stored name 'Amazon (SJC14)' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136302` (event 1601) | loose | job_count 33 matches neither a component row nor the notice total 555; row date is 116 day(s) after the notice date; stored name 'Amazon (SJC13)' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136301` (event 1600) | loose | job_count 28 matches neither a component row nor the notice total 555; row date is 116 day(s) after the notice date; stored name 'Amazon (SJC11)' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136300` (event 1599) | loose | job_count 138 matches neither a component row nor the notice total 555; row date is 116 day(s) after the notice date; stored name 'Amazon (SJC10)' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136299` (event 1598) | loose | job_count 65 matches neither a component row nor the notice total 555; row date is 116 day(s) after the notice date; stored name 'Amazon LAX78' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136298` (event 1597) | loose | job_count 3 matches neither a component row nor the notice total 555; row date is 116 day(s) after the notice date; stored name 'Amazon LAX16' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136297` (event 1596) | loose | job_count 62 matches neither a component row nor the notice total 555; row date is 116 day(s) after the notice date; stored name 'Amazon LAX10' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136296` (event 1595) | loose | job_count 43 matches neither a component row nor the notice total 555; row date is 116 day(s) after the notice date; stored name 'Amazon LAX21' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `136295` (event 1594) | loose | job_count 65 matches neither a component row nor the notice total 555; row date is 116 day(s) after the notice date; stored name 'Amazon LAX22' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135392` (event 1168) | loose | job_count 84 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon - SFO 28' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135391` (event 1167) | loose | job_count 19 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon - SFO 13' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135390` (event 1166) | loose | job_count 1 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon - SAN 3' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135389` (event 1165) | loose | job_count 2 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon - SAN 21' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135388` (event 1164) | loose | job_count 13 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon - SAN 18' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135387` (event 1163) | loose | job_count 19 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon - SAN 17' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135386` (event 1162) | loose | job_count 1 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon - SAN 15' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135385` (event 1161) | loose | job_count 38 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon - SAN 13' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135384` (event 1160) | loose | job_count 34 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon - SNA 3' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135383` (event 1159) | loose | job_count 25 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon - SNA 20' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135382` (event 1158) | loose | job_count 1 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon - SNA 17' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135381` (event 1157) | loose | job_count 24 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon - SNA 16' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135380` (event 1156) | loose | job_count 5 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon - SNA12' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135371` (event 1147) | loose | job_count 49 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon (SJC44)' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135370` (event 1146) | loose | job_count 141 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon (SJC38)' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135369` (event 1145) | loose | job_count 43 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon (SJC25)' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135368` (event 1144) | loose | job_count 45 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon (LAX78)' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135367` (event 1143) | loose | job_count 46 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon (LAX16)' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135366` (event 1142) | loose | job_count 2 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon (LAX10)' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135365` (event 1141) | loose | job_count 139 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon - MAM7' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135364` (event 1140) | loose | job_count 189 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon - MAO6' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135363` (event 1139) | loose | job_count 190 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon - MAF5' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135362` (event 1138) | loose | job_count 163 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon - MAQ8' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135361` (event 1137) | loose | job_count 179 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon - MAM9' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135360` (event 1136) | loose | job_count 160 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon - MAJ8' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135359` (event 1135) | loose | job_count 182 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon - MAI8' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135358` (event 1134) | loose | job_count 172 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon - MAH8' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135357` (event 1133) | loose | job_count 174 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon - MAQ9' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135356` (event 1132) | loose | job_count 181 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon - MBA6' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135355` (event 1131) | loose | job_count 175 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon - MAC2' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135354` (event 1130) | loose | job_count 191 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon - MAB9' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135353` (event 1129) | loose | job_count 191 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon - MAB8' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135352` (event 1128) | loose | job_count 134 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon - MAK9' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135351` (event 1127) | loose | job_count 185 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon - MAG1' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135350` (event 1126) | loose | job_count 155 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon - MAF9' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135349` (event 1125) | loose | job_count 196 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon - MAF8' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135348` (event 1124) | loose | job_count 201 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon - MAF3' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135347` (event 1123) | loose | job_count 168 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon - MAC9' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135346` (event 1122) | loose | job_count 184 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon - MAB5' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135345` (event 1121) | loose | job_count 131 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon - MAB4' differs from the published 'Amazon' |
| 11 | CA | [Amazon](#11-ca-amazon) 2025-10-02 | 555 | `135344` (event 1120) | loose | job_count 215 matches neither a component row nor the notice total 555; row date is 208 day(s) after the notice date; stored name 'Amazon - MAB1' differs from the published 'Amazon' |
| 12 | CA | [Manna Beverages MBV-CA LLC - 1226](#12-ca-manna-beverages-mbv-ca-llc---1226) 2025-10-03 | 638 | `137337` (event 2223) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 12 | CA | [Manna Beverages MBV-CA LLC - 1226](#12-ca-manna-beverages-mbv-ca-llc---1226) 2025-10-03 | 638 | `137342` (event 2228) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Manna Beverages MBV-CA LLC 3685' differs from the published 'Manna Beverages MBV-CA LLC - 1226' |
| 12 | CA | [Manna Beverages MBV-CA LLC - 1226](#12-ca-manna-beverages-mbv-ca-llc---1226) 2025-10-03 | 638 | `137341` (event 2227) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Manna Beverages MBV-CA LLC 3600' differs from the published 'Manna Beverages MBV-CA LLC - 1226' |
| 12 | CA | [Manna Beverages MBV-CA LLC - 1226](#12-ca-manna-beverages-mbv-ca-llc---1226) 2025-10-03 | 638 | `137340` (event 2226) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Manna Beverages MBV-CA LLC 2286' differs from the published 'Manna Beverages MBV-CA LLC - 1226' |
| 12 | CA | [Manna Beverages MBV-CA LLC - 1226](#12-ca-manna-beverages-mbv-ca-llc---1226) 2025-10-03 | 638 | `137339` (event 2225) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Manna Beverages MBV-CA LLC - 2150' differs from the published 'Manna Beverages MBV-CA LLC - 1226' |
| 12 | CA | [Manna Beverages MBV-CA LLC - 1226](#12-ca-manna-beverages-mbv-ca-llc---1226) 2025-10-03 | 638 | `137338` (event 2224) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Manna Beverages MBV-CA LLC 6725' differs from the published 'Manna Beverages MBV-CA LLC - 1226' |
| 13 | CA | [SAP America, Inc.](#13-ca-sap-america--inc) 2025-10-06 | 82 | `136946` (event 2006) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 14 | CA | [Jet Propulsion Laboratory (California Instit](#14-ca-jet-propulsion-laboratory--california-institute-of) 2025-10-14 | 543 | `136767` (event 1915) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 15 | CA | [Centene Management Company, LLC](#15-ca-centene-management-company--llc) 2025-10-20 | 5 | `136710` (event 1881) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 16 | CA | [Ojai Valley Inn](#16-ca-ojai-valley-inn) 2025-10-20 | 773 | `136478` (event 1714) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 17 | CA | [Amazon SFO12](#17-ca-amazon-sfo12) 2025-10-28 | 18 | `136306` (event 1605) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136300` (event 1599) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136333` (event 1632) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon (SFO38)' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136332` (event 1631) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon (SFO28)' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136331` (event 1630) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon (SFO19)' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136330` (event 1629) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon (SFO13)' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136329` (event 1628) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon (ONM213)' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136328` (event 1627) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon (ONM212)' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136327` (event 1626) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon (SAN 5)' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136326` (event 1625) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon (SAN 3)' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136325` (event 1624) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon (SAN 21)' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136324` (event 1623) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon (SAN 18)' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136323` (event 1622) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon (SAN 17)' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136322` (event 1621) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon (SAN 15)' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136321` (event 1620) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon (SAN 13)' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136318` (event 1617) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon SNA18' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136313` (event 1612) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon SJC44' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136312` (event 1611) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon SJC38' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136306` (event 1605) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon SFO12' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136305` (event 1604) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon (SJC32)' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136304` (event 1603) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon (SJC31)' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136303` (event 1602) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon (SJC14)' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136302` (event 1601) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon (SJC13)' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136301` (event 1600) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon (SJC11)' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136298` (event 1597) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon LAX16' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135390` (event 1166) | exact | job_count equals one published component row of this notice; row date is 182 day(s) after the notice date; stored name 'Amazon - SAN 3' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135386` (event 1162) | exact | job_count equals one published component row of this notice; row date is 182 day(s) after the notice date; stored name 'Amazon - SAN 15' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135382` (event 1158) | exact | job_count equals one published component row of this notice; row date is 182 day(s) after the notice date; stored name 'Amazon - SNA 17' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135381` (event 1157) | exact | job_count equals one published component row of this notice; row date is 182 day(s) after the notice date; stored name 'Amazon - SNA 16' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135380` (event 1156) | exact | job_count equals one published component row of this notice; row date is 182 day(s) after the notice date; stored name 'Amazon - SNA12' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135374` (event 1150) | exact | job_count equals one published component row of this notice; row date is 182 day(s) after the notice date; stored name 'Amazon' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136455` (event 1705) | loose | job_count 173 matches neither a component row nor the notice total 673; row date is 70 day(s) after the notice date; stored name 'Amazon' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136454` (event 1704) | loose | job_count 126 matches neither a component row nor the notice total 673; row date is 70 day(s) after the notice date; stored name 'Amazon' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136453` (event 1703) | loose | job_count 107 matches neither a component row nor the notice total 673; row date is 70 day(s) after the notice date; stored name 'Amazon' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136452` (event 1702) | loose | job_count 149 matches neither a component row nor the notice total 673; row date is 70 day(s) after the notice date; stored name 'Amazon' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136320` (event 1619) | loose | job_count 45 matches neither a component row nor the notice total 673; row date equals this notice's earliest published effective date; stored name 'Amazon SNA3' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136319` (event 1618) | loose | job_count 16 matches neither a component row nor the notice total 673; row date equals this notice's earliest published effective date; stored name 'Amazon SNA19' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136317` (event 1616) | loose | job_count 12 matches neither a component row nor the notice total 673; row date equals this notice's earliest published effective date; stored name 'Amazon SNA17' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136316` (event 1615) | loose | job_count 64 matches neither a component row nor the notice total 673; row date equals this notice's earliest published effective date; stored name 'Amazon SNA16' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136315` (event 1614) | loose | job_count 17 matches neither a component row nor the notice total 673; row date equals this notice's earliest published effective date; stored name 'Amazon SNA12' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136314` (event 1613) | loose | job_count 178 matches neither a component row nor the notice total 673; row date equals this notice's earliest published effective date; stored name 'Amazon SNA11' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136311` (event 1610) | loose | job_count 8 matches neither a component row nor the notice total 673; row date equals this notice's earliest published effective date; stored name 'Amazon SJC25' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136310` (event 1609) | loose | job_count 2 matches neither a component row nor the notice total 673; row date equals this notice's earliest published effective date; stored name 'Amazon SFO39' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136309` (event 1608) | loose | job_count 12 matches neither a component row nor the notice total 673; row date equals this notice's earliest published effective date; stored name 'Amazon SFO36' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136308` (event 1607) | loose | job_count 75 matches neither a component row nor the notice total 673; row date equals this notice's earliest published effective date; stored name 'Amazon SFO24' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136307` (event 1606) | loose | job_count 69 matches neither a component row nor the notice total 673; row date equals this notice's earliest published effective date; stored name 'Amazon SFO22' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136299` (event 1598) | loose | job_count 65 matches neither a component row nor the notice total 673; row date equals this notice's earliest published effective date; stored name 'Amazon LAX78' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136297` (event 1596) | loose | job_count 62 matches neither a component row nor the notice total 673; row date equals this notice's earliest published effective date; stored name 'Amazon LAX10' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136296` (event 1595) | loose | job_count 43 matches neither a component row nor the notice total 673; row date equals this notice's earliest published effective date; stored name 'Amazon LAX21' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `136295` (event 1594) | loose | job_count 65 matches neither a component row nor the notice total 673; row date equals this notice's earliest published effective date; stored name 'Amazon LAX22' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135392` (event 1168) | loose | job_count 84 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon - SFO 28' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135391` (event 1167) | loose | job_count 19 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon - SFO 13' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135389` (event 1165) | loose | job_count 2 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon - SAN 21' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135388` (event 1164) | loose | job_count 13 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon - SAN 18' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135387` (event 1163) | loose | job_count 19 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon - SAN 17' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135385` (event 1161) | loose | job_count 38 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon - SAN 13' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135384` (event 1160) | loose | job_count 34 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon - SNA 3' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135383` (event 1159) | loose | job_count 25 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon - SNA 20' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135379` (event 1155) | loose | job_count 89 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135378` (event 1154) | loose | job_count 81 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135377` (event 1153) | loose | job_count 87 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135376` (event 1152) | loose | job_count 58 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135375` (event 1151) | loose | job_count 11 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135373` (event 1149) | loose | job_count 32 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135372` (event 1148) | loose | job_count 72 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135371` (event 1147) | loose | job_count 49 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon (SJC44)' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135370` (event 1146) | loose | job_count 141 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon (SJC38)' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135369` (event 1145) | loose | job_count 43 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon (SJC25)' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135368` (event 1144) | loose | job_count 45 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon (LAX78)' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135367` (event 1143) | loose | job_count 46 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon (LAX16)' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135366` (event 1142) | loose | job_count 2 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon (LAX10)' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135365` (event 1141) | loose | job_count 139 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon - MAM7' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135364` (event 1140) | loose | job_count 189 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon - MAO6' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135363` (event 1139) | loose | job_count 190 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon - MAF5' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135362` (event 1138) | loose | job_count 163 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon - MAQ8' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135361` (event 1137) | loose | job_count 179 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon - MAM9' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135360` (event 1136) | loose | job_count 160 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon - MAJ8' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135359` (event 1135) | loose | job_count 182 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon - MAI8' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135358` (event 1134) | loose | job_count 172 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon - MAH8' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135357` (event 1133) | loose | job_count 174 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon - MAQ9' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135356` (event 1132) | loose | job_count 181 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon - MBA6' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135355` (event 1131) | loose | job_count 175 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon - MAC2' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135354` (event 1130) | loose | job_count 191 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon - MAB9' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135353` (event 1129) | loose | job_count 191 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon - MAB8' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135352` (event 1128) | loose | job_count 134 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon - MAK9' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135351` (event 1127) | loose | job_count 185 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon - MAG1' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135350` (event 1126) | loose | job_count 155 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon - MAF9' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135349` (event 1125) | loose | job_count 196 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon - MAF8' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135348` (event 1124) | loose | job_count 201 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon - MAF3' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135347` (event 1123) | loose | job_count 168 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon - MAC9' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135346` (event 1122) | loose | job_count 184 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon - MAB5' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135345` (event 1121) | loose | job_count 131 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon - MAB4' differs from the published 'Amazon (SJC10)' |
| 18 | CA | [Amazon (SJC10)](#18-ca-amazon--sjc10) 2025-10-28 | 673 | `135344` (event 1120) | loose | job_count 215 matches neither a component row nor the notice total 673; row date is 182 day(s) after the notice date; stored name 'Amazon - MAB1' differs from the published 'Amazon (SJC10)' |
| 19 | CA | [Educational Testing Service (ETS)](#19-ca-educational-testing-service--ets) 2025-10-30 | 757 | `136584` (event 1811) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136516` (event 1750) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136556` (event 1790) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)' |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136555` (event 1789) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)' |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136554` (event 1788) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)' |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136553` (event 1787) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)' |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136552` (event 1786) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)' |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136551` (event 1785) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)' |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136550` (event 1784) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)' |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136549` (event 1783) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)' |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136548` (event 1782) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Fresno Economic Opportunities Commission (5104 N. West)' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)' |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136547` (event 1781) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)' |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136546` (event 1780) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)' |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136545` (event 1779) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)' |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136544` (event 1778) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Fresno Economic Opportunities Commission (4273 W. Richert, Ave, 107)' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)' |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136543` (event 1777) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)' |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136542` (event 1776) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)' |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136541` (event 1775) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)' |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136540` (event 1774) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Fresno Economic Opportunities Commission (3110 W. Nielsen)' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)' |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136539` (event 1773) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)' |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136538` (event 1772) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)' |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136537` (event 1771) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)' |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136536` (event 1770) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)' |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136535` (event 1769) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)' |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136534` (event 1768) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)' |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136533` (event 1767) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)' |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136532` (event 1766) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)' |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136531` (event 1765) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)' |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136530` (event 1764) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)' |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136529` (event 1763) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)' |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136528` (event 1762) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Fresno Economic Opportunities Commission (1620 W. Fairmont)' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)' |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136527` (event 1761) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Fresno Economic Opportunities Commission (1504 N. Webser)' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)' |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136526` (event 1760) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Fresno Economic Opportunities Commission (1441 Divisadero)' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)' |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136525` (event 1759) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)' |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136524` (event 1758) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)' |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136523` (event 1757) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Fresno Economic Opportunities Commission (1350 E. Annadale)' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)' |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136522` (event 1756) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)' |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136521` (event 1755) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Fresno Economic Opportunities Commission (1240 E. Washington)' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)' |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136520` (event 1754) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)' |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136519` (event 1753) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)' |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136518` (event 1752) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)' |
| 20 | CA | [Fresno Economic Opportunities Commission (11](#20-ca-fresno-economic-opportunities-commission--1101-e) 2025-10-31 | 639 | `136517` (event 1751) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)' |
| 21 | CA | [Mattel, Inc.](#21-ca-mattel--inc) 2025-11-13 | 89 | `136421` (event 1684) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 21 | CA | [Mattel, Inc.](#21-ca-mattel--inc) 2025-11-13 | 89 | `135083` (event 983) | loose | job_count 65 matches neither a component row nor the notice total 89; row date is 190 day(s) after the notice date |
| 22 | CA | [Terzo Enterprises Incorporated](#22-ca-terzo-enterprises-incorporated) 2025-12-01 | 58 | `136246` (event 1582) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 23 | CA | [Wabash National LP](#23-ca-wabash-national-lp) 2026-01-05 | 100 | `135967` (event 1467) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 23 | CA | [Wabash National LP](#23-ca-wabash-national-lp) 2026-01-05 | 100 | `135966` (event 1466) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 24 | CA | [Autodesk](#24-ca-autodesk) 2026-01-23 | 104 | `135682` (event 1318) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 25 | CA | [Amazon - MAB1](#25-ca-amazon---mab1) 2026-01-28 | 3,855 | `135344` (event 1120) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135366` (event 1142) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136333` (event 1632) | exact | job_count equals one published component row of this notice; row date is -3 day(s) after the notice date; stored name 'Amazon (SFO38)' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136329` (event 1628) | exact | job_count equals one published component row of this notice; row date is -3 day(s) after the notice date; stored name 'Amazon (ONM213)' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136328` (event 1627) | exact | job_count equals one published component row of this notice; row date is -3 day(s) after the notice date; stored name 'Amazon (ONM212)' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136327` (event 1626) | exact | job_count equals one published component row of this notice; row date is -3 day(s) after the notice date; stored name 'Amazon (SAN 5)' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136326` (event 1625) | exact | job_count equals one published component row of this notice; row date is -3 day(s) after the notice date; stored name 'Amazon (SAN 3)' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136325` (event 1624) | exact | job_count equals one published component row of this notice; row date is -3 day(s) after the notice date; stored name 'Amazon (SAN 21)' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136324` (event 1623) | exact | job_count equals one published component row of this notice; row date is -3 day(s) after the notice date; stored name 'Amazon (SAN 18)' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136321` (event 1620) | exact | job_count equals one published component row of this notice; row date is -3 day(s) after the notice date; stored name 'Amazon (SAN 13)' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136320` (event 1619) | exact | job_count equals one published component row of this notice; row date is -3 day(s) after the notice date; stored name 'Amazon SNA3' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136318` (event 1617) | exact | job_count equals one published component row of this notice; row date is -3 day(s) after the notice date; stored name 'Amazon SNA18' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136310` (event 1609) | exact | job_count equals one published component row of this notice; row date is -3 day(s) after the notice date; stored name 'Amazon SFO39' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136298` (event 1597) | exact | job_count equals one published component row of this notice; row date is -3 day(s) after the notice date; stored name 'Amazon LAX16' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136296` (event 1595) | exact | job_count equals one published component row of this notice; row date is -3 day(s) after the notice date; stored name 'Amazon LAX21' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135392` (event 1168) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon - SFO 28' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135391` (event 1167) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon - SFO 13' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135390` (event 1166) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon - SAN 3' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135389` (event 1165) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon - SAN 21' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135388` (event 1164) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon - SAN 18' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135387` (event 1163) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon - SAN 17' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135386` (event 1162) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon - SAN 15' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135385` (event 1161) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon - SAN 13' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135384` (event 1160) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon - SNA 3' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135383` (event 1159) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon - SNA 20' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135382` (event 1158) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon - SNA 17' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135381` (event 1157) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon - SNA 16' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135380` (event 1156) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon - SNA12' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135379` (event 1155) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135378` (event 1154) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135377` (event 1153) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135376` (event 1152) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135375` (event 1151) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135374` (event 1150) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135373` (event 1149) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135372` (event 1148) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135371` (event 1147) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon (SJC44)' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135370` (event 1146) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon (SJC38)' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135369` (event 1145) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon (SJC25)' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135368` (event 1144) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon (LAX78)' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135367` (event 1143) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon (LAX16)' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136455` (event 1705) | loose | job_count 173 matches neither a component row nor the notice total 1025; row date is -23 day(s) after the notice date; stored name 'Amazon' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136454` (event 1704) | loose | job_count 126 matches neither a component row nor the notice total 1025; row date is -23 day(s) after the notice date; stored name 'Amazon' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136453` (event 1703) | loose | job_count 107 matches neither a component row nor the notice total 1025; row date is -23 day(s) after the notice date; stored name 'Amazon' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136452` (event 1702) | loose | job_count 149 matches neither a component row nor the notice total 1025; row date is -23 day(s) after the notice date; stored name 'Amazon' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136332` (event 1631) | loose | job_count 71 matches neither a component row nor the notice total 1025; row date is -3 day(s) after the notice date; stored name 'Amazon (SFO28)' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136331` (event 1630) | loose | job_count 18 matches neither a component row nor the notice total 1025; row date is -3 day(s) after the notice date; stored name 'Amazon (SFO19)' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136330` (event 1629) | loose | job_count 41 matches neither a component row nor the notice total 1025; row date is -3 day(s) after the notice date; stored name 'Amazon (SFO13)' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136323` (event 1622) | loose | job_count 61 matches neither a component row nor the notice total 1025; row date is -3 day(s) after the notice date; stored name 'Amazon (SAN 17)' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136322` (event 1621) | loose | job_count 50 matches neither a component row nor the notice total 1025; row date is -3 day(s) after the notice date; stored name 'Amazon (SAN 15)' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136319` (event 1618) | loose | job_count 16 matches neither a component row nor the notice total 1025; row date is -3 day(s) after the notice date; stored name 'Amazon SNA19' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136317` (event 1616) | loose | job_count 12 matches neither a component row nor the notice total 1025; row date is -3 day(s) after the notice date; stored name 'Amazon SNA17' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136316` (event 1615) | loose | job_count 64 matches neither a component row nor the notice total 1025; row date is -3 day(s) after the notice date; stored name 'Amazon SNA16' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136315` (event 1614) | loose | job_count 17 matches neither a component row nor the notice total 1025; row date is -3 day(s) after the notice date; stored name 'Amazon SNA12' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136314` (event 1613) | loose | job_count 178 matches neither a component row nor the notice total 1025; row date is -3 day(s) after the notice date; stored name 'Amazon SNA11' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136313` (event 1612) | loose | job_count 18 matches neither a component row nor the notice total 1025; row date is -3 day(s) after the notice date; stored name 'Amazon SJC44' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136312` (event 1611) | loose | job_count 50 matches neither a component row nor the notice total 1025; row date is -3 day(s) after the notice date; stored name 'Amazon SJC38' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136311` (event 1610) | loose | job_count 8 matches neither a component row nor the notice total 1025; row date is -3 day(s) after the notice date; stored name 'Amazon SJC25' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136309` (event 1608) | loose | job_count 12 matches neither a component row nor the notice total 1025; row date is -3 day(s) after the notice date; stored name 'Amazon SFO36' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136308` (event 1607) | loose | job_count 75 matches neither a component row nor the notice total 1025; row date is -3 day(s) after the notice date; stored name 'Amazon SFO24' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136307` (event 1606) | loose | job_count 69 matches neither a component row nor the notice total 1025; row date is -3 day(s) after the notice date; stored name 'Amazon SFO22' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136306` (event 1605) | loose | job_count 18 matches neither a component row nor the notice total 1025; row date is -3 day(s) after the notice date; stored name 'Amazon SFO12' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136305` (event 1604) | loose | job_count 85 matches neither a component row nor the notice total 1025; row date is -3 day(s) after the notice date; stored name 'Amazon (SJC32)' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136304` (event 1603) | loose | job_count 27 matches neither a component row nor the notice total 1025; row date is -3 day(s) after the notice date; stored name 'Amazon (SJC31)' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136303` (event 1602) | loose | job_count 80 matches neither a component row nor the notice total 1025; row date is -3 day(s) after the notice date; stored name 'Amazon (SJC14)' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136302` (event 1601) | loose | job_count 33 matches neither a component row nor the notice total 1025; row date is -3 day(s) after the notice date; stored name 'Amazon (SJC13)' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136301` (event 1600) | loose | job_count 28 matches neither a component row nor the notice total 1025; row date is -3 day(s) after the notice date; stored name 'Amazon (SJC11)' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136300` (event 1599) | loose | job_count 138 matches neither a component row nor the notice total 1025; row date is -3 day(s) after the notice date; stored name 'Amazon (SJC10)' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136299` (event 1598) | loose | job_count 65 matches neither a component row nor the notice total 1025; row date is -3 day(s) after the notice date; stored name 'Amazon LAX78' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136297` (event 1596) | loose | job_count 62 matches neither a component row nor the notice total 1025; row date is -3 day(s) after the notice date; stored name 'Amazon LAX10' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `136295` (event 1594) | loose | job_count 65 matches neither a component row nor the notice total 1025; row date is -3 day(s) after the notice date; stored name 'Amazon LAX22' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135365` (event 1141) | loose | job_count 139 matches neither a component row nor the notice total 1025; row date equals this notice's earliest published effective date; stored name 'Amazon - MAM7' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135364` (event 1140) | loose | job_count 189 matches neither a component row nor the notice total 1025; row date equals this notice's earliest published effective date; stored name 'Amazon - MAO6' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135363` (event 1139) | loose | job_count 190 matches neither a component row nor the notice total 1025; row date equals this notice's earliest published effective date; stored name 'Amazon - MAF5' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135362` (event 1138) | loose | job_count 163 matches neither a component row nor the notice total 1025; row date equals this notice's earliest published effective date; stored name 'Amazon - MAQ8' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135361` (event 1137) | loose | job_count 179 matches neither a component row nor the notice total 1025; row date equals this notice's earliest published effective date; stored name 'Amazon - MAM9' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135360` (event 1136) | loose | job_count 160 matches neither a component row nor the notice total 1025; row date equals this notice's earliest published effective date; stored name 'Amazon - MAJ8' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135359` (event 1135) | loose | job_count 182 matches neither a component row nor the notice total 1025; row date equals this notice's earliest published effective date; stored name 'Amazon - MAI8' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135358` (event 1134) | loose | job_count 172 matches neither a component row nor the notice total 1025; row date equals this notice's earliest published effective date; stored name 'Amazon - MAH8' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135357` (event 1133) | loose | job_count 174 matches neither a component row nor the notice total 1025; row date equals this notice's earliest published effective date; stored name 'Amazon - MAQ9' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135356` (event 1132) | loose | job_count 181 matches neither a component row nor the notice total 1025; row date equals this notice's earliest published effective date; stored name 'Amazon - MBA6' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135355` (event 1131) | loose | job_count 175 matches neither a component row nor the notice total 1025; row date equals this notice's earliest published effective date; stored name 'Amazon - MAC2' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135354` (event 1130) | loose | job_count 191 matches neither a component row nor the notice total 1025; row date equals this notice's earliest published effective date; stored name 'Amazon - MAB9' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135353` (event 1129) | loose | job_count 191 matches neither a component row nor the notice total 1025; row date equals this notice's earliest published effective date; stored name 'Amazon - MAB8' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135352` (event 1128) | loose | job_count 134 matches neither a component row nor the notice total 1025; row date equals this notice's earliest published effective date; stored name 'Amazon - MAK9' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135351` (event 1127) | loose | job_count 185 matches neither a component row nor the notice total 1025; row date equals this notice's earliest published effective date; stored name 'Amazon - MAG1' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135350` (event 1126) | loose | job_count 155 matches neither a component row nor the notice total 1025; row date equals this notice's earliest published effective date; stored name 'Amazon - MAF9' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135349` (event 1125) | loose | job_count 196 matches neither a component row nor the notice total 1025; row date equals this notice's earliest published effective date; stored name 'Amazon - MAF8' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135348` (event 1124) | loose | job_count 201 matches neither a component row nor the notice total 1025; row date equals this notice's earliest published effective date; stored name 'Amazon - MAF3' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135347` (event 1123) | loose | job_count 168 matches neither a component row nor the notice total 1025; row date equals this notice's earliest published effective date; stored name 'Amazon - MAC9' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135346` (event 1122) | loose | job_count 184 matches neither a component row nor the notice total 1025; row date equals this notice's earliest published effective date; stored name 'Amazon - MAB5' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135345` (event 1121) | loose | job_count 131 matches neither a component row nor the notice total 1025; row date equals this notice's earliest published effective date; stored name 'Amazon - MAB4' differs from the published 'Amazon (LAX10)' |
| 26 | CA | [Amazon (LAX10)](#26-ca-amazon--lax10) 2026-01-29 | 1,025 | `135344` (event 1120) | loose | job_count 215 matches neither a component row nor the notice total 1025; row date equals this notice's earliest published effective date; stored name 'Amazon - MAB1' differs from the published 'Amazon (LAX10)' |
| 27 | CA | [Del Monte Foods Corporation II Inc - Modesto](#27-ca-del-monte-foods-corporation-ii-inc---modesto) 2026-01-30 | 776 | `135621` (event 1282) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 27 | CA | [Del Monte Foods Corporation II Inc - Modesto](#27-ca-del-monte-foods-corporation-ii-inc---modesto) 2026-01-30 | 776 | `135622` (event 1283) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Del Monte Foods Corporation II Inc. - Hughson' differs from the published 'Del Monte Foods Corporation II Inc - Modesto' |
| 27 | CA | [Del Monte Foods Corporation II Inc - Modesto](#27-ca-del-monte-foods-corporation-ii-inc---modesto) 2026-01-30 | 776 | `135625` (event 1286) | loose | job_count 25 matches neither a component row nor the notice total 776; row date equals this notice's earliest published effective date; stored name 'Del Monte Foods Corporation II Inc.' differs from the published 'Del Monte Foods Corporation II Inc - Modesto' |
| 27 | CA | [Del Monte Foods Corporation II Inc - Modesto](#27-ca-del-monte-foods-corporation-ii-inc---modesto) 2026-01-30 | 776 | `135264` (event 1083) | loose | job_count 21 matches neither a component row nor the notice total 776; row date is 91 day(s) after the notice date; stored name 'Del Monte Foods Corporation II Inc.' differs from the published 'Del Monte Foods Corporation II Inc - Modesto' |
| 28 | CA | [First Brands Group, LLC](#28-ca-first-brands-group--llc) 2026-02-03 | 98 | `135649` (event 1297) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 29 | CA | [Raley's](#29-ca-raley-s) 2026-02-20 | 43 | `135393` (event 1169) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 30 | CA | [KBR Services LLC](#30-ca-kbr-services-llc) 2026-03-06 | 758 | `135210` (event 1064) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 30 | CA | [KBR Services LLC](#30-ca-kbr-services-llc) 2026-03-06 | 758 | `134247` (event 483) | loose | job_count 650 matches neither a component row nor the notice total 758; row date is 148 day(s) after the notice date |
| 31 | CA | [MAG Brand Group, LLC](#31-ca-mag-brand-group--llc) 2026-03-25 | 53 | `134246` (event 482) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 32 | CA | [Oracle America, Inc.](#32-ca-oracle-america--inc) 2026-04-01 | 702 | `134962` (event 913) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 32 | CA | [Oracle America, Inc.](#32-ca-oracle-america--inc) 2026-04-01 | 702 | `134961` (event 912) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 32 | CA | [Oracle America, Inc.](#32-ca-oracle-america--inc) 2026-04-01 | 702 | `134960` (event 911) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 32 | CA | [Oracle America, Inc.](#32-ca-oracle-america--inc) 2026-04-01 | 702 | `134958` (event 909) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 33 | CA | [Wellpath and CFMG - South Placer Jail](#33-ca-wellpath-and-cfmg---south-placer-jail) 2026-04-07 | 89 | `134537` (event 661) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 33 | CA | [Wellpath and CFMG - South Placer Jail](#33-ca-wellpath-and-cfmg---south-placer-jail) 2026-04-07 | 89 | `134539` (event 663) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Wellpath and CFMG - Placer Juvi Detention' differs from the published 'Wellpath and CFMG - South Placer Jail' |
| 33 | CA | [Wellpath and CFMG - South Placer Jail](#33-ca-wellpath-and-cfmg---south-placer-jail) 2026-04-07 | 89 | `134538` (event 662) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Wellpath and CFMG - Placer Jail - Auburn' differs from the published 'Wellpath and CFMG - South Placer Jail' |
| 34 | CA | [YMCA Juan Pacifico Ontiveros Elementary Scho](#34-ca-ymca-juan-pacifico-ontiveros-elementary-school) 2026-04-17 | 10 | `134867` (event 855) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 35 | CA | [Geodis](#35-ca-geodis) 2026-04-28 | 238 | `134477` (event 617) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 35 | CA | [Geodis](#35-ca-geodis) 2026-04-28 | 238 | `134037` (event 43966) | loose | job_count 81 matches neither a component row nor the notice total 238; row date is 128 day(s) after the notice date |
| 36 | CA | [Boys & Girls Club at the LA Harbor - Narbonn](#36-ca-boys---girls-club-at-the-la-harbor---narbonne-high) 2026-05-13 | 2 | `134852` (event 843) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 36 | CA | [Boys & Girls Club at the LA Harbor - Narbonn](#36-ca-boys---girls-club-at-the-la-harbor---narbonne-high) 2026-05-13 | 2 | `134851` (event 842) | loose | job_count 10 matches neither a component row nor the notice total 2; row date equals this notice's earliest published effective date; stored name 'Boys &Girls Club of the La Harbor - Harbor City Elementary School' differs from the published 'Boys & Girls Club at the LA Harbor - Narbonne High School' |
| 36 | CA | [Boys & Girls Club at the LA Harbor - Narbonn](#36-ca-boys---girls-club-at-the-la-harbor---narbonne-high) 2026-05-13 | 2 | `134850` (event 841) | loose | job_count 7 matches neither a component row nor the notice total 2; row date equals this notice's earliest published effective date; stored name 'Boys & Girls Club of the LA Harbor - Fleming Middle School' differs from the published 'Boys & Girls Club at the LA Harbor - Narbonne High School' |
| 36 | CA | [Boys & Girls Club at the LA Harbor - Narbonn](#36-ca-boys---girls-club-at-the-la-harbor---narbonne-high) 2026-05-13 | 2 | `134849` (event 840) | loose | job_count 4 matches neither a component row nor the notice total 2; row date equals this notice's earliest published effective date; stored name 'Boys & Girls Club of the LA Harbor - Environmental Charter MS' differs from the published 'Boys & Girls Club at the LA Harbor - Narbonne High School' |
| 36 | CA | [Boys & Girls Club at the LA Harbor - Narbonn](#36-ca-boys---girls-club-at-the-la-harbor---narbonne-high) 2026-05-13 | 2 | `134848` (event 839) | loose | job_count 1 matches neither a component row nor the notice total 2; row date equals this notice's earliest published effective date; stored name 'Boys & Girls Club of the La Harbor - Cheryl Green/Torrance Club' differs from the published 'Boys & Girls Club at the LA Harbor - Narbonne High School' |
| 36 | CA | [Boys & Girls Club at the LA Harbor - Narbonn](#36-ca-boys---girls-club-at-the-la-harbor---narbonne-high) 2026-05-13 | 2 | `134846` (event 837) | loose | job_count 8 matches neither a component row nor the notice total 2; row date equals this notice's earliest published effective date; stored name 'Boys & Girls Club of the LA Harbor - Taper Ave. Elementary' differs from the published 'Boys & Girls Club at the LA Harbor - Narbonne High School' |
| 36 | CA | [Boys & Girls Club at the LA Harbor - Narbonn](#36-ca-boys---girls-club-at-the-la-harbor---narbonne-high) 2026-05-13 | 2 | `134845` (event 836) | loose | job_count 3 matches neither a component row nor the notice total 2; row date equals this notice's earliest published effective date; stored name 'Boys & Girls Club of the LA Harbor - South Shores Elementary' differs from the published 'Boys & Girls Club at the LA Harbor - Narbonne High School' |
| 36 | CA | [Boys & Girls Club at the LA Harbor - Narbonn](#36-ca-boys---girls-club-at-the-la-harbor---narbonne-high) 2026-05-13 | 2 | `134844` (event 835) | loose | job_count 5 matches neither a component row nor the notice total 2; row date equals this notice's earliest published effective date; stored name 'Boys & Girls Club of LA Harbor - Point Fermin Elementary' differs from the published 'Boys & Girls Club at the LA Harbor - Narbonne High School' |
| 36 | CA | [Boys & Girls Club at the LA Harbor - Narbonn](#36-ca-boys---girls-club-at-the-la-harbor---narbonne-high) 2026-05-13 | 2 | `134843` (event 834) | loose | job_count 8 matches neither a component row nor the notice total 2; row date equals this notice's earliest published effective date; stored name 'Boys & Girls Club of the LA Harbor - Park Western Elementary' differs from the published 'Boys & Girls Club at the LA Harbor - Narbonne High School' |
| 36 | CA | [Boys & Girls Club at the LA Harbor - Narbonn](#36-ca-boys---girls-club-at-the-la-harbor---narbonne-high) 2026-05-13 | 2 | `134842` (event 833) | loose | job_count 3 matches neither a component row nor the notice total 2; row date equals this notice's earliest published effective date; stored name 'Boys & Girls Club of the LA Harbor - Dana Middle School' differs from the published 'Boys & Girls Club at the LA Harbor - Narbonne High School' |
| 36 | CA | [Boys & Girls Club at the LA Harbor - Narbonn](#36-ca-boys---girls-club-at-the-la-harbor---narbonne-high) 2026-05-13 | 2 | `134841` (event 832) | loose | job_count 3 matches neither a component row nor the notice total 2; row date equals this notice's earliest published effective date; stored name 'Boys & Girls Club of the LA Harbor - Barton Hill Elementary' differs from the published 'Boys & Girls Club at the LA Harbor - Narbonne High School' |
| 36 | CA | [Boys & Girls Club at the LA Harbor - Narbonn](#36-ca-boys---girls-club-at-the-la-harbor---narbonne-high) 2026-05-13 | 2 | `134840` (event 831) | loose | job_count 3 matches neither a component row nor the notice total 2; row date equals this notice's earliest published effective date; stored name 'Boys & Girls Club of LA Harbor - Wilmington Park ES' differs from the published 'Boys & Girls Club at the LA Harbor - Narbonne High School' |
| 36 | CA | [Boys & Girls Club at the LA Harbor - Narbonn](#36-ca-boys---girls-club-at-the-la-harbor---narbonne-high) 2026-05-13 | 2 | `134839` (event 830) | loose | job_count 3 matches neither a component row nor the notice total 2; row date equals this notice's earliest published effective date; stored name 'Boys & Girls Club of the LA Harbor - Wilmington Club' differs from the published 'Boys & Girls Club at the LA Harbor - Narbonne High School' |
| 36 | CA | [Boys & Girls Club at the LA Harbor - Narbonn](#36-ca-boys---girls-club-at-the-la-harbor---narbonne-high) 2026-05-13 | 2 | `134838` (event 829) | loose | job_count 7 matches neither a component row nor the notice total 2; row date equals this notice's earliest published effective date; stored name 'Boys & Girls Club of the LA Harbor - Harbor Teacher Prep Academy' differs from the published 'Boys & Girls Club at the LA Harbor - Narbonne High School' |
| 36 | CA | [Boys & Girls Club at the LA Harbor - Narbonn](#36-ca-boys---girls-club-at-the-la-harbor---narbonne-high) 2026-05-13 | 2 | `134837` (event 828) | loose | job_count 3 matches neither a component row nor the notice total 2; row date equals this notice's earliest published effective date; stored name 'Boys & Girls Club of LA Harbor - Harry Bridges Span School' differs from the published 'Boys & Girls Club at the LA Harbor - Narbonne High School' |
| 36 | CA | [Boys & Girls Club at the LA Harbor - Narbonn](#36-ca-boys---girls-club-at-the-la-harbor---narbonne-high) 2026-05-13 | 2 | `134836` (event 827) | loose | job_count 1 matches neither a component row nor the notice total 2; row date equals this notice's earliest published effective date; stored name 'Boys & Girls Club of the LA Harbor - Gulf Ave Elementary' differs from the published 'Boys & Girls Club at the LA Harbor - Narbonne High School' |
| 36 | CA | [Boys & Girls Club at the LA Harbor - Narbonn](#36-ca-boys---girls-club-at-the-la-harbor---narbonne-high) 2026-05-13 | 2 | `134834` (event 825) | loose | job_count 5 matches neither a component row nor the notice total 2; row date equals this notice's earliest published effective date; stored name 'Boys & Girls Club of the LA Harbor - Banning High' differs from the published 'Boys & Girls Club at the LA Harbor - Narbonne High School' |
| 37 | CA | [LinkedIn Corporation](#37-ca-linkedin-corporation) 2026-05-15 | 606 | `134428` (event 590) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 37 | CA | [LinkedIn Corporation](#37-ca-linkedin-corporation) 2026-05-15 | 606 | `134427` (event 589) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 37 | CA | [LinkedIn Corporation](#37-ca-linkedin-corporation) 2026-05-15 | 606 | `134426` (event 588) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 37 | CA | [LinkedIn Corporation](#37-ca-linkedin-corporation) 2026-05-15 | 606 | `134425` (event 587) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 37 | CA | [LinkedIn Corporation](#37-ca-linkedin-corporation) 2026-05-15 | 606 | `134429` (event 591) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'LinkedIn Corporation (Home Office)' differs from the published 'LinkedIn Corporation' |
| 38 | CA | [TeamOne](#38-ca-teamone) 2026-05-18 | 725 | `134797` (event 804) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 39 | CA | [Intuit Inc.](#39-ca-intuit-inc) 2026-05-20 | 910 | `134259` (event 491) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 39 | CA | [Intuit Inc.](#39-ca-intuit-inc) 2026-05-20 | 910 | `134258` (event 490) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 39 | CA | [Intuit Inc.](#39-ca-intuit-inc) 2026-05-20 | 910 | `134257` (event 489) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 39 | CA | [Intuit Inc.](#39-ca-intuit-inc) 2026-05-20 | 910 | `134255` (event 487) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 40 | CA | [Meta Platforms, Inc.](#40-ca-meta-platforms--inc) 2026-05-22 | 3,270 | `135027` (event 950) | exact | job_count equals one published component row of this notice; row date is 7 day(s) after the notice date |
| 40 | CA | [Meta Platforms, Inc.](#40-ca-meta-platforms--inc) 2026-05-22 | 3,270 | `134372` (event 560) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 40 | CA | [Meta Platforms, Inc.](#40-ca-meta-platforms--inc) 2026-05-22 | 3,270 | `134371` (event 559) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 40 | CA | [Meta Platforms, Inc.](#40-ca-meta-platforms--inc) 2026-05-22 | 3,270 | `134370` (event 558) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 40 | CA | [Meta Platforms, Inc.](#40-ca-meta-platforms--inc) 2026-05-22 | 3,270 | `134369` (event 557) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 40 | CA | [Meta Platforms, Inc.](#40-ca-meta-platforms--inc) 2026-05-22 | 3,270 | `134368` (event 556) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 40 | CA | [Meta Platforms, Inc.](#40-ca-meta-platforms--inc) 2026-05-22 | 3,270 | `134367` (event 555) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 40 | CA | [Meta Platforms, Inc.](#40-ca-meta-platforms--inc) 2026-05-22 | 3,270 | `135085` (event 985) | loose | job_count 124 matches neither a component row nor the notice total 3270; row date is 0 day(s) after the notice date |
| 41 | CA | [KBR Services LLC](#41-ca-kbr-services-llc) 2026-05-24 | 650 | `134247` (event 483) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 41 | CA | [KBR Services LLC](#41-ca-kbr-services-llc) 2026-05-24 | 650 | `135210` (event 1064) | loose | job_count 758 matches neither a component row nor the notice total 650; row date is -18 day(s) after the notice date |
| 42 | CA | [Tricor Industrial, Inc DBA Astrolite Alloys](#42-ca-tricor-industrial--inc-dba-astrolite-alloys) 2026-05-29 | 6 | `134264` (event 496) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 43 | CA | [Vine Hospitality (LB Steak Bishop Ranch, LP)](#43-ca-vine-hospitality--lb-steak-bishop-ranch--lp) 2026-06-21 | 365 | `134718` (event 767) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 43 | CA | [Vine Hospitality (LB Steak Bishop Ranch, LP)](#43-ca-vine-hospitality--lb-steak-bishop-ranch--lp) 2026-06-21 | 365 | `134725` (event 774) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Vine Hospitality (Vine Dining Enterprises, Inc)' differs from the published 'Vine Hospitality (LB Steak Bishop Ranch, LP)' |
| 43 | CA | [Vine Hospitality (LB Steak Bishop Ranch, LP)](#43-ca-vine-hospitality--lb-steak-bishop-ranch--lp) 2026-06-21 | 365 | `134724` (event 773) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Vine Hospitality (Santana Grill Partners, LP)' differs from the published 'Vine Hospitality (LB Steak Bishop Ranch, LP)' |
| 43 | CA | [Vine Hospitality (LB Steak Bishop Ranch, LP)](#43-ca-vine-hospitality--lb-steak-bishop-ranch--lp) 2026-06-21 | 365 | `134723` (event 772) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Vine Hospitality (La Rive Gauche San Jose, LLC)' differs from the published 'Vine Hospitality (LB Steak Bishop Ranch, LP)' |
| 43 | CA | [Vine Hospitality (LB Steak Bishop Ranch, LP)](#43-ca-vine-hospitality--lb-steak-bishop-ranch--lp) 2026-06-21 | 365 | `134722` (event 771) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Vine Hospitality (Meso Santana Row, LP)' differs from the published 'Vine Hospitality (LB Steak Bishop Ranch, LP)' |
| 43 | CA | [Vine Hospitality (LB Steak Bishop Ranch, LP)](#43-ca-vine-hospitality--lb-steak-bishop-ranch--lp) 2026-06-21 | 365 | `134721` (event 770) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Vine Hospitality (Left Bank Menlo Park Partners, LP)' differs from the published 'Vine Hospitality (LB Steak Bishop Ranch, LP)' |
| 43 | CA | [Vine Hospitality (LB Steak Bishop Ranch, LP)](#43-ca-vine-hospitality--lb-steak-bishop-ranch--lp) 2026-06-21 | 365 | `134720` (event 769) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Vine Hospitality (Blue Rock Restaurant Partners, LP)' differs from the published 'Vine Hospitality (LB Steak Bishop Ranch, LP)' |
| 43 | CA | [Vine Hospitality (LB Steak Bishop Ranch, LP)](#43-ca-vine-hospitality--lb-steak-bishop-ranch--lp) 2026-06-21 | 365 | `134719` (event 768) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Vine Hospitality (Left Bank Tiburon, LP)' differs from the published 'Vine Hospitality (LB Steak Bishop Ranch, LP)' |
| 44 | TN | [BlueCross BlueShield of Tennessee, Inc.](#44-tn-bluecross-blueshield-of-tennessee--inc) 2025-07-02 | 150 | `137751` (event 2471) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 45 | TN | [GEODIS Logistics, LLC](#45-tn-geodis-logistics--llc) 2025-07-24 | 57 | `137485` (event 2320) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 45 | TN | [GEODIS Logistics, LLC](#45-tn-geodis-logistics--llc) 2025-07-24 | 57 | `138049` (event 2608) | loose | job_count 40 matches neither a component row nor the notice total 57; row date is 7 day(s) after the notice date |
| 46 | TN | [FedEx Supply Chain](#46-tn-fedex-supply-chain) 2025-08-27 | 611 | `137315` (event 2211) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 47 | TN | [DoubleTree by Memphis](#47-tn-doubletree-by-memphis) 2025-09-30 | 88 | `136884` (event 1970) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 48 | TN | [OP Mobility](#48-tn-op-mobility) 2025-10-07 | 82 | `136950` (event 2009) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 49 | TN | [Crescent Park Corporation](#49-tn-crescent-park-corporation) 2025-10-17 | 76 | `136715` (event 1883) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 50 | TN | [HD Supply](#50-tn-hd-supply) 2025-10-27 | 108 | `136439` (event 1695) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 51 | TN | [GM - Ultium Cells Facility](#51-tn-gm---ultium-cells-facility) 2025-10-30 | 710 | `136470` (event 1712) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 52 | TN | [Creative Dining Services, Inc.](#52-tn-creative-dining-services--inc) 2025-11-07 | 100 | `136769` (event 1916) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 53 | TN | [Edgewell Personal Care](#53-tn-edgewell-personal-care) 2025-11-14 | 132 | `134968` (event 916) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 54 | TN | [Kroger Fulfillment Network LLC](#54-tn-kroger-fulfillment-network-llc) 2025-12-03 | 132 | `136213` (event 1574) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 55 | TN | [Archer Daniels Midland Company](#55-tn-archer-daniels-midland-company) 2025-12-19 | 95 | `136254` (event 1585) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 56 | TN | [Linamar Shelbyville](#56-tn-linamar-shelbyville) 2026-01-13 | 80 | `136415` (event 42247) | exact | job_count equals one published component row of this notice; row date is 0 day(s) after the notice date |
| 57 | TN | [Smoky Mountain Logistics, LLC](#57-tn-smoky-mountain-logistics--llc) 2026-01-26 | 100 | `136338` (event 42238) | exact | job_count equals one published component row of this notice; row date is 0 day(s) after the notice date |
| 58 | TN | [NIKE Retail Services, Inc.](#58-tn-nike-retail-services--inc) 2026-01-27 | 583 | `136293` (event 42236) | exact | job_count equals one published component row of this notice; row date is 0 day(s) after the notice date |
| 59 | TN | [DLH Solutions](#59-tn-dlh-solutions) 2026-01-30 | 209 | `135751` (event 1365) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 60 | TN | [Premiere Building Maintenance Corporation](#60-tn-premiere-building-maintenance-corporation) 2026-02-03 | 154 | `135752` (event 1366) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 61 | TN | [Liberty Dental Plan](#61-tn-liberty-dental-plan) 2026-02-19 | 1 | `135635` (event 1294) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 62 | TN | [McKay Books, Inc.](#62-tn-mckay-books--inc) 2026-03-02 | 54 | `136015` (event 42216) | exact | job_count equals one published component row of this notice; row date is 0 day(s) after the notice date |
| 63 | TN | [First Brands Group, LLC](#63-tn-first-brands-group--llc) 2026-03-04 | 333 | `136003` (event 42214) | exact | job_count equals one published component row of this notice; row date is 0 day(s) after the notice date |
| 64 | TN | [IKEA Memphis](#64-tn-ikea-memphis) 2026-03-05 | 114 | `135997` (event 42212) | exact | job_count equals one published component row of this notice; row date is 0 day(s) after the notice date |
| 65 | TN | [Blount Memorial Hospital](#65-tn-blount-memorial-hospital) 2026-03-24 | 85 | `135814` (event 42188) | exact | job_count equals one published component row of this notice; row date is 0 day(s) after the notice date |
| 66 | TN | [Durham School Services](#66-tn-durham-school-services) 2026-04-10 | 79 | `135592` (event 42175) | exact | job_count equals one published component row of this notice; row date is 0 day(s) after the notice date |
| 67 | TN | [Pave It Forward Logistics](#67-tn-pave-it-forward-logistics) 2026-04-15 | 100 | `135536` (event 42170) | exact | job_count equals one published component row of this notice; row date is 0 day(s) after the notice date |
| 68 | TN | [Adient](#68-tn-adient) 2026-04-21 | 210 | `135470` (event 42159) | exact | job_count equals one published component row of this notice; row date is 0 day(s) after the notice date |
| 69 | TN | [Fayette County Public Schools](#69-tn-fayette-county-public-schools) 2026-05-04 | 75 | `135237` (event 42133) | exact | job_count equals one published component row of this notice; row date is 0 day(s) after the notice date |
| 70 | TX | [International Business Machines-Coppell](#70-tx-international-business-machines-coppell) 2025-07-02 | 59 | `137811` (event 110646) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 71 | TX | [Intel Corporation](#71-tx-intel-corporation) 2025-07-09 | 110 | `138170` (event 111005) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 72 | TX | [SM Cargo](#72-tx-sm-cargo) 2025-07-21 | 194 | `137593` (event 110428) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 73 | TX | [Chevron Corporation (HESS Corporation)](#73-tx-chevron-corporation--hess-corporation) 2025-07-21 | 575 | `137555` (event 110390) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 73 | TX | [Chevron Corporation (HESS Corporation)](#73-tx-chevron-corporation--hess-corporation) 2025-07-21 | 575 | `138173` (event 111008) | loose | job_count 185 matches neither a component row nor the notice total 575; row date is -6 day(s) after the notice date; stored name 'Chevron (Deauville Blvd)' differs from the published 'Chevron Corporation (HESS Corporation)' |
| 73 | TX | [Chevron Corporation (HESS Corporation)](#73-tx-chevron-corporation--hess-corporation) 2025-07-21 | 575 | `138172` (event 111007) | loose | job_count 1 matches neither a component row nor the notice total 575; row date is -6 day(s) after the notice date; stored name 'Chevron (S. County Rd.)' differs from the published 'Chevron Corporation (HESS Corporation)' |
| 73 | TX | [Chevron Corporation (HESS Corporation)](#73-tx-chevron-corporation--hess-corporation) 2025-07-21 | 575 | `138171` (event 111006) | loose | job_count 14 matches neither a component row nor the notice total 575; row date is -6 day(s) after the notice date; stored name 'Chevron (N. FM 1788)' differs from the published 'Chevron Corporation (HESS Corporation)' |
| 74 | TX | [Equus Workforce Solutions Stephenville (Arbo](#74-tx-equus-workforce-solutions-stephenville--arbor-e-t) 2025-07-30 | 2 | `137507` (event 110342) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 74 | TX | [Equus Workforce Solutions Stephenville (Arbo](#74-tx-equus-workforce-solutions-stephenville--arbor-e-t) 2025-07-30 | 2 | `137511` (event 110346) | loose | job_count 4 matches neither a component row nor the notice total 2; row date equals this notice's earliest published effective date; stored name 'Equus Workforce Solutions Arlington (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions Stephenville (Arbor E&T, LLC)' |
| 74 | TX | [Equus Workforce Solutions Stephenville (Arbo](#74-tx-equus-workforce-solutions-stephenville--arbor-e-t) 2025-07-30 | 2 | `137510` (event 110345) | loose | job_count 27 matches neither a component row nor the notice total 2; row date equals this notice's earliest published effective date; stored name 'Equus Workforce Solutions Denton (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions Stephenville (Arbor E&T, LLC)' |
| 74 | TX | [Equus Workforce Solutions Stephenville (Arbo](#74-tx-equus-workforce-solutions-stephenville--arbor-e-t) 2025-07-30 | 2 | `137509` (event 110344) | loose | job_count 9 matches neither a component row nor the notice total 2; row date equals this notice's earliest published effective date; stored name 'Equus Workforce Solutions Greenville (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions Stephenville (Arbor E&T, LLC)' |
| 74 | TX | [Equus Workforce Solutions Stephenville (Arbo](#74-tx-equus-workforce-solutions-stephenville--arbor-e-t) 2025-07-30 | 2 | `137508` (event 110343) | loose | job_count 15 matches neither a component row nor the notice total 2; row date equals this notice's earliest published effective date; stored name 'Equus Workforce Solutions McKinney (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions Stephenville (Arbor E&T, LLC)' |
| 74 | TX | [Equus Workforce Solutions Stephenville (Arbo](#74-tx-equus-workforce-solutions-stephenville--arbor-e-t) 2025-07-30 | 2 | `137506` (event 110341) | loose | job_count 8 matches neither a component row nor the notice total 2; row date equals this notice's earliest published effective date; stored name 'Equus Workforce Solutions Terrell (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions Stephenville (Arbor E&T, LLC)' |
| 74 | TX | [Equus Workforce Solutions Stephenville (Arbo](#74-tx-equus-workforce-solutions-stephenville--arbor-e-t) 2025-07-30 | 2 | `137505` (event 110340) | loose | job_count 16 matches neither a component row nor the notice total 2; row date equals this notice's earliest published effective date; stored name 'Equus Workforce Solutions Weatherford (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions Stephenville (Arbor E&T, LLC)' |
| 74 | TX | [Equus Workforce Solutions Stephenville (Arbo](#74-tx-equus-workforce-solutions-stephenville--arbor-e-t) 2025-07-30 | 2 | `137504` (event 110339) | loose | job_count 1 matches neither a component row nor the notice total 2; row date equals this notice's earliest published effective date; stored name 'Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions Stephenville (Arbor E&T, LLC)' |
| 74 | TX | [Equus Workforce Solutions Stephenville (Arbo](#74-tx-equus-workforce-solutions-stephenville--arbor-e-t) 2025-07-30 | 2 | `137503` (event 110338) | loose | job_count 10 matches neither a component row nor the notice total 2; row date equals this notice's earliest published effective date; stored name 'Equus Workforce Solutions-N.Tenth St. (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions Stephenville (Arbor E&T, LLC)' |
| 74 | TX | [Equus Workforce Solutions Stephenville (Arbo](#74-tx-equus-workforce-solutions-stephenville--arbor-e-t) 2025-07-30 | 2 | `137502` (event 110337) | loose | job_count 71 matches neither a component row nor the notice total 2; row date equals this notice's earliest published effective date; stored name 'Equus Workforce Solutions-Highway 161. (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions Stephenville (Arbor E&T, LLC)' |
| 74 | TX | [Equus Workforce Solutions Stephenville (Arbo](#74-tx-equus-workforce-solutions-stephenville--arbor-e-t) 2025-07-30 | 2 | `137501` (event 110336) | loose | job_count 10 matches neither a component row nor the notice total 2; row date equals this notice's earliest published effective date; stored name 'Equus Workforce Solutions-Greenville Ave. (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions Stephenville (Arbor E&T, LLC)' |
| 74 | TX | [Equus Workforce Solutions Stephenville (Arbo](#74-tx-equus-workforce-solutions-stephenville--arbor-e-t) 2025-07-30 | 2 | `137500` (event 110335) | loose | job_count 13 matches neither a component row nor the notice total 2; row date equals this notice's earliest published effective date; stored name 'Equus Workforce Solutions-Irving Blvd. (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions Stephenville (Arbor E&T, LLC)' |
| 74 | TX | [Equus Workforce Solutions Stephenville (Arbo](#74-tx-equus-workforce-solutions-stephenville--arbor-e-t) 2025-07-30 | 2 | `137499` (event 110334) | loose | job_count 17 matches neither a component row nor the notice total 2; row date equals this notice's earliest published effective date; stored name 'Equus Workforce Solutions-Alpha Rd.(Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions Stephenville (Arbor E&T, LLC)' |
| 74 | TX | [Equus Workforce Solutions Stephenville (Arbo](#74-tx-equus-workforce-solutions-stephenville--arbor-e-t) 2025-07-30 | 2 | `137498` (event 110333) | loose | job_count 16 matches neither a component row nor the notice total 2; row date equals this notice's earliest published effective date; stored name 'Equus Workforce Solutions-Malcolm X Blvd.(Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions Stephenville (Arbor E&T, LLC)' |
| 74 | TX | [Equus Workforce Solutions Stephenville (Arbo](#74-tx-equus-workforce-solutions-stephenville--arbor-e-t) 2025-07-30 | 2 | `137497` (event 110332) | loose | job_count 16 matches neither a component row nor the notice total 2; row date equals this notice's earliest published effective date; stored name 'Equus Workforce Solutions-Buckner Blvd.(Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions Stephenville (Arbor E&T, LLC)' |
| 74 | TX | [Equus Workforce Solutions Stephenville (Arbo](#74-tx-equus-workforce-solutions-stephenville--arbor-e-t) 2025-07-30 | 2 | `137494` (event 110329) | loose | job_count 12 matches neither a component row nor the notice total 2; row date equals this notice's earliest published effective date; stored name 'Equus Workforce Solutions Houston Opertions- Acres Home (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions Stephenville (Arbor E&T, LLC)' |
| 74 | TX | [Equus Workforce Solutions Stephenville (Arbo](#74-tx-equus-workforce-solutions-stephenville--arbor-e-t) 2025-07-30 | 2 | `137493` (event 110328) | loose | job_count 13 matches neither a component row nor the notice total 2; row date equals this notice's earliest published effective date; stored name 'Equus Workforce Solutions Houston Opertions- Pearland (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions Stephenville (Arbor E&T, LLC)' |
| 74 | TX | [Equus Workforce Solutions Stephenville (Arbo](#74-tx-equus-workforce-solutions-stephenville--arbor-e-t) 2025-07-30 | 2 | `137492` (event 110327) | loose | job_count 28 matches neither a component row nor the notice total 2; row date equals this notice's earliest published effective date; stored name 'Equus Workforce Solutions Houston Opertions- Westheimer Rd. (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions Stephenville (Arbor E&T, LLC)' |
| 75 | TX | [Equus Workforce Solutions-Camp Wisdom (Arbor](#75-tx-equus-workforce-solutions-camp-wisdom--arbor-e-t) 2025-07-31 | 1 | `137504` (event 110339) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 75 | TX | [Equus Workforce Solutions-Camp Wisdom (Arbor](#75-tx-equus-workforce-solutions-camp-wisdom--arbor-e-t) 2025-07-31 | 1 | `137511` (event 110346) | loose | job_count 4 matches neither a component row nor the notice total 1; row date equals this notice's earliest published effective date; stored name 'Equus Workforce Solutions Arlington (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC)' |
| 75 | TX | [Equus Workforce Solutions-Camp Wisdom (Arbor](#75-tx-equus-workforce-solutions-camp-wisdom--arbor-e-t) 2025-07-31 | 1 | `137510` (event 110345) | loose | job_count 27 matches neither a component row nor the notice total 1; row date equals this notice's earliest published effective date; stored name 'Equus Workforce Solutions Denton (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC)' |
| 75 | TX | [Equus Workforce Solutions-Camp Wisdom (Arbor](#75-tx-equus-workforce-solutions-camp-wisdom--arbor-e-t) 2025-07-31 | 1 | `137509` (event 110344) | loose | job_count 9 matches neither a component row nor the notice total 1; row date equals this notice's earliest published effective date; stored name 'Equus Workforce Solutions Greenville (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC)' |
| 75 | TX | [Equus Workforce Solutions-Camp Wisdom (Arbor](#75-tx-equus-workforce-solutions-camp-wisdom--arbor-e-t) 2025-07-31 | 1 | `137508` (event 110343) | loose | job_count 15 matches neither a component row nor the notice total 1; row date equals this notice's earliest published effective date; stored name 'Equus Workforce Solutions McKinney (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC)' |
| 75 | TX | [Equus Workforce Solutions-Camp Wisdom (Arbor](#75-tx-equus-workforce-solutions-camp-wisdom--arbor-e-t) 2025-07-31 | 1 | `137507` (event 110342) | loose | job_count 2 matches neither a component row nor the notice total 1; row date equals this notice's earliest published effective date; stored name 'Equus Workforce Solutions Stephenville (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC)' |
| 75 | TX | [Equus Workforce Solutions-Camp Wisdom (Arbor](#75-tx-equus-workforce-solutions-camp-wisdom--arbor-e-t) 2025-07-31 | 1 | `137506` (event 110341) | loose | job_count 8 matches neither a component row nor the notice total 1; row date equals this notice's earliest published effective date; stored name 'Equus Workforce Solutions Terrell (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC)' |
| 75 | TX | [Equus Workforce Solutions-Camp Wisdom (Arbor](#75-tx-equus-workforce-solutions-camp-wisdom--arbor-e-t) 2025-07-31 | 1 | `137505` (event 110340) | loose | job_count 16 matches neither a component row nor the notice total 1; row date equals this notice's earliest published effective date; stored name 'Equus Workforce Solutions Weatherford (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC)' |
| 75 | TX | [Equus Workforce Solutions-Camp Wisdom (Arbor](#75-tx-equus-workforce-solutions-camp-wisdom--arbor-e-t) 2025-07-31 | 1 | `137503` (event 110338) | loose | job_count 10 matches neither a component row nor the notice total 1; row date equals this notice's earliest published effective date; stored name 'Equus Workforce Solutions-N.Tenth St. (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC)' |
| 75 | TX | [Equus Workforce Solutions-Camp Wisdom (Arbor](#75-tx-equus-workforce-solutions-camp-wisdom--arbor-e-t) 2025-07-31 | 1 | `137502` (event 110337) | loose | job_count 71 matches neither a component row nor the notice total 1; row date equals this notice's earliest published effective date; stored name 'Equus Workforce Solutions-Highway 161. (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC)' |
| 75 | TX | [Equus Workforce Solutions-Camp Wisdom (Arbor](#75-tx-equus-workforce-solutions-camp-wisdom--arbor-e-t) 2025-07-31 | 1 | `137501` (event 110336) | loose | job_count 10 matches neither a component row nor the notice total 1; row date equals this notice's earliest published effective date; stored name 'Equus Workforce Solutions-Greenville Ave. (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC)' |
| 75 | TX | [Equus Workforce Solutions-Camp Wisdom (Arbor](#75-tx-equus-workforce-solutions-camp-wisdom--arbor-e-t) 2025-07-31 | 1 | `137500` (event 110335) | loose | job_count 13 matches neither a component row nor the notice total 1; row date equals this notice's earliest published effective date; stored name 'Equus Workforce Solutions-Irving Blvd. (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC)' |
| 75 | TX | [Equus Workforce Solutions-Camp Wisdom (Arbor](#75-tx-equus-workforce-solutions-camp-wisdom--arbor-e-t) 2025-07-31 | 1 | `137499` (event 110334) | loose | job_count 17 matches neither a component row nor the notice total 1; row date equals this notice's earliest published effective date; stored name 'Equus Workforce Solutions-Alpha Rd.(Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC)' |
| 75 | TX | [Equus Workforce Solutions-Camp Wisdom (Arbor](#75-tx-equus-workforce-solutions-camp-wisdom--arbor-e-t) 2025-07-31 | 1 | `137498` (event 110333) | loose | job_count 16 matches neither a component row nor the notice total 1; row date equals this notice's earliest published effective date; stored name 'Equus Workforce Solutions-Malcolm X Blvd.(Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC)' |
| 75 | TX | [Equus Workforce Solutions-Camp Wisdom (Arbor](#75-tx-equus-workforce-solutions-camp-wisdom--arbor-e-t) 2025-07-31 | 1 | `137497` (event 110332) | loose | job_count 16 matches neither a component row nor the notice total 1; row date equals this notice's earliest published effective date; stored name 'Equus Workforce Solutions-Buckner Blvd.(Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC)' |
| 75 | TX | [Equus Workforce Solutions-Camp Wisdom (Arbor](#75-tx-equus-workforce-solutions-camp-wisdom--arbor-e-t) 2025-07-31 | 1 | `137494` (event 110329) | loose | job_count 12 matches neither a component row nor the notice total 1; row date equals this notice's earliest published effective date; stored name 'Equus Workforce Solutions Houston Opertions- Acres Home (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC)' |
| 75 | TX | [Equus Workforce Solutions-Camp Wisdom (Arbor](#75-tx-equus-workforce-solutions-camp-wisdom--arbor-e-t) 2025-07-31 | 1 | `137493` (event 110328) | loose | job_count 13 matches neither a component row nor the notice total 1; row date equals this notice's earliest published effective date; stored name 'Equus Workforce Solutions Houston Opertions- Pearland (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC)' |
| 75 | TX | [Equus Workforce Solutions-Camp Wisdom (Arbor](#75-tx-equus-workforce-solutions-camp-wisdom--arbor-e-t) 2025-07-31 | 1 | `137492` (event 110327) | loose | job_count 28 matches neither a component row nor the notice total 1; row date equals this notice's earliest published effective date; stored name 'Equus Workforce Solutions Houston Opertions- Westheimer Rd. (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC)' |
| 76 | TX | [Planned Parenthood Gulf Coast (Prevention Pa](#76-tx-planned-parenthood-gulf-coast--prevention-park-fac) 2025-07-31 | 114 | `137495` (event 110330) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 77 | TX | [Southwest Key Programs, Inc. (Casa Houston R](#77-tx-southwest-key-programs--inc---casa-houston-reliant) 2025-07-31 | 1,213 | `137377` (event 110212) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 77 | TX | [Southwest Key Programs, Inc. (Casa Houston R](#77-tx-southwest-key-programs--inc---casa-houston-reliant) 2025-07-31 | 1,213 | `137376` (event 110211) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Southwest Key Programs, Inc. (Houston HQ)' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)' |
| 77 | TX | [Southwest Key Programs, Inc. (Casa Houston R](#77-tx-southwest-key-programs--inc---casa-houston-reliant) 2025-07-31 | 1,213 | `137375` (event 110210) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Southwest Key Programs, Inc. (Casa Quetzal)' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)' |
| 77 | TX | [Southwest Key Programs, Inc. (Casa Houston R](#77-tx-southwest-key-programs--inc---casa-houston-reliant) 2025-07-31 | 1,213 | `137374` (event 110209) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Southwest Key Programs, Inc. (Casa Sunzal)' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)' |
| 77 | TX | [Southwest Key Programs, Inc. (Casa Houston R](#77-tx-southwest-key-programs--inc---casa-houston-reliant) 2025-07-31 | 1,213 | `137373` (event 110208) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Southwest Key Programs, Inc. (Casa Oasis)' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)' |
| 77 | TX | [Southwest Key Programs, Inc. (Casa Houston R](#77-tx-southwest-key-programs--inc---casa-houston-reliant) 2025-07-31 | 1,213 | `137372` (event 110207) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Southwest Key Programs, Inc. (Casa Sueno)' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)' |
| 77 | TX | [Southwest Key Programs, Inc. (Casa Houston R](#77-tx-southwest-key-programs--inc---casa-houston-reliant) 2025-07-31 | 1,213 | `137371` (event 110206) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Southwest Key Programs, Inc. (Casa Montezuma)' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)' |
| 77 | TX | [Southwest Key Programs, Inc. (Casa Houston R](#77-tx-southwest-key-programs--inc---casa-houston-reliant) 2025-07-31 | 1,213 | `137370` (event 110205) | loose | job_count 4 matches neither a component row nor the notice total 1213; row date equals this notice's earliest published effective date; stored name 'Southwest Key Programs, Inc. La Esperanza)' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)' |
| 77 | TX | [Southwest Key Programs, Inc. (Casa Houston R](#77-tx-southwest-key-programs--inc---casa-houston-reliant) 2025-07-31 | 1,213 | `137369` (event 110204) | loose | job_count 9 matches neither a component row nor the notice total 1213; row date equals this notice's earliest published effective date; stored name 'Southwest Key Programs, Inc.(Casa Nueva Esperanza)' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)' |
| 77 | TX | [Southwest Key Programs, Inc. (Casa Houston R](#77-tx-southwest-key-programs--inc---casa-houston-reliant) 2025-07-31 | 1,213 | `137368` (event 110203) | loose | job_count 13 matches neither a component row nor the notice total 1213; row date equals this notice's earliest published effective date; stored name 'Southwest Key Programs, Inc.(South Texas HQ)' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)' |
| 77 | TX | [Southwest Key Programs, Inc. (Casa Houston R](#77-tx-southwest-key-programs--inc---casa-houston-reliant) 2025-07-31 | 1,213 | `137367` (event 110202) | loose | job_count 1 matches neither a component row nor the notice total 1213; row date equals this notice's earliest published effective date; stored name 'Southwest Key Programs, Inc. (Casa Franklin)' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)' |
| 77 | TX | [Southwest Key Programs, Inc. (Casa Houston R](#77-tx-southwest-key-programs--inc---casa-houston-reliant) 2025-07-31 | 1,213 | `137366` (event 110201) | loose | job_count 3 matches neither a component row nor the notice total 1213; row date equals this notice's earliest published effective date; stored name 'Southwest Key Programs, Inc. (Casa Norma Linda)' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)' |
| 77 | TX | [Southwest Key Programs, Inc. (Casa Houston R](#77-tx-southwest-key-programs--inc---casa-houston-reliant) 2025-07-31 | 1,213 | `137365` (event 110200) | loose | job_count 3 matches neither a component row nor the notice total 1213; row date equals this notice's earliest published effective date; stored name 'Southwest Key Programs, Inc. (Casa Rio Grande)' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)' |
| 77 | TX | [Southwest Key Programs, Inc. (Casa Houston R](#77-tx-southwest-key-programs--inc---casa-houston-reliant) 2025-07-31 | 1,213 | `137364` (event 110199) | loose | job_count 3 matches neither a component row nor the notice total 1213; row date equals this notice's earliest published effective date; stored name 'Southwest Key Programs, Inc. (Casa Canutillo)' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)' |
| 77 | TX | [Southwest Key Programs, Inc. (Casa Houston R](#77-tx-southwest-key-programs--inc---casa-houston-reliant) 2025-07-31 | 1,213 | `137359` (event 110194) | loose | job_count 45 matches neither a component row nor the notice total 1213; row date is 67 day(s) after the notice date; stored name 'Southwest Key Programs, Inc. (SWK National Headquarters)' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)' |
| 77 | TX | [Southwest Key Programs, Inc. (Casa Houston R](#77-tx-southwest-key-programs--inc---casa-houston-reliant) 2025-07-31 | 1,213 | `137093` (event 109928) | loose | job_count 2 matches neither a component row nor the notice total 1213; row date is 97 day(s) after the notice date; stored name 'Southwest Key Programs-Casa Canutillo' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)' |
| 77 | TX | [Southwest Key Programs, Inc. (Casa Houston R](#77-tx-southwest-key-programs--inc---casa-houston-reliant) 2025-07-31 | 1,213 | `137092` (event 109927) | loose | job_count 5 matches neither a component row nor the notice total 1213; row date is 97 day(s) after the notice date; stored name 'Southwest Key Programs-Casita Del Valle' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)' |
| 77 | TX | [Southwest Key Programs, Inc. (Casa Houston R](#77-tx-southwest-key-programs--inc---casa-houston-reliant) 2025-07-31 | 1,213 | `137091` (event 109926) | loose | job_count 1 matches neither a component row nor the notice total 1213; row date is 97 day(s) after the notice date; stored name 'Southwest Key Programs-Casa Houston Reliant' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)' |
| 77 | TX | [Southwest Key Programs, Inc. (Casa Houston R](#77-tx-southwest-key-programs--inc---casa-houston-reliant) 2025-07-31 | 1,213 | `137090` (event 109925) | loose | job_count 1 matches neither a component row nor the notice total 1213; row date is 97 day(s) after the notice date; stored name 'Southwest Key Programs-Casa Montezuma' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)' |
| 77 | TX | [Southwest Key Programs, Inc. (Casa Houston R](#77-tx-southwest-key-programs--inc---casa-houston-reliant) 2025-07-31 | 1,213 | `137089` (event 109924) | loose | job_count 3 matches neither a component row nor the notice total 1213; row date is 97 day(s) after the notice date; stored name 'Southwest Key Programs-Casa Norma Linda' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)' |
| 77 | TX | [Southwest Key Programs, Inc. (Casa Houston R](#77-tx-southwest-key-programs--inc---casa-houston-reliant) 2025-07-31 | 1,213 | `137088` (event 109923) | loose | job_count 8 matches neither a component row nor the notice total 1213; row date is 97 day(s) after the notice date; stored name 'Southwest Key Programs-Casa Nueva Esperanza' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)' |
| 77 | TX | [Southwest Key Programs, Inc. (Casa Houston R](#77-tx-southwest-key-programs--inc---casa-houston-reliant) 2025-07-31 | 1,213 | `137087` (event 109922) | loose | job_count 3 matches neither a component row nor the notice total 1213; row date is 97 day(s) after the notice date; stored name 'Southwest Key Programs-Casa Rio Grande' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)' |
| 77 | TX | [Southwest Key Programs, Inc. (Casa Houston R](#77-tx-southwest-key-programs--inc---casa-houston-reliant) 2025-07-31 | 1,213 | `137086` (event 109921) | loose | job_count 3 matches neither a component row nor the notice total 1213; row date is 97 day(s) after the notice date; stored name 'Southwest Key Programs-National Headquarters (Austin)' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)' |
| 77 | TX | [Southwest Key Programs, Inc. (Casa Houston R](#77-tx-southwest-key-programs--inc---casa-houston-reliant) 2025-07-31 | 1,213 | `137085` (event 109920) | loose | job_count 12 matches neither a component row nor the notice total 1213; row date is 97 day(s) after the notice date; stored name 'Southwest Key Programs-STX Regional Headquarters' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)' |
| 77 | TX | [Southwest Key Programs, Inc. (Casa Houston R](#77-tx-southwest-key-programs--inc---casa-houston-reliant) 2025-07-31 | 1,213 | `137084` (event 109919) | loose | job_count 10 matches neither a component row nor the notice total 1213; row date is 97 day(s) after the notice date; stored name 'Southwest Key Programs-Houston Headquarters' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)' |
| 78 | TX | [Southwest Key Programs, Inc. La Esperanza)](#78-tx-southwest-key-programs--inc--la-esperanza) 2025-08-06 | 4 | `137370` (event 110205) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 78 | TX | [Southwest Key Programs, Inc. La Esperanza)](#78-tx-southwest-key-programs--inc--la-esperanza) 2025-08-06 | 4 | `137377` (event 110212) | loose | job_count 211 matches neither a component row nor the notice total 4; row date equals this notice's earliest published effective date; stored name 'Southwest Key Programs, Inc. (Casa Houston Reliant)' differs from the published 'Southwest Key Programs, Inc. La Esperanza)' |
| 78 | TX | [Southwest Key Programs, Inc. La Esperanza)](#78-tx-southwest-key-programs--inc--la-esperanza) 2025-08-06 | 4 | `137376` (event 110211) | loose | job_count 11 matches neither a component row nor the notice total 4; row date equals this notice's earliest published effective date; stored name 'Southwest Key Programs, Inc. (Houston HQ)' differs from the published 'Southwest Key Programs, Inc. La Esperanza)' |
| 78 | TX | [Southwest Key Programs, Inc. La Esperanza)](#78-tx-southwest-key-programs--inc--la-esperanza) 2025-08-06 | 4 | `137375` (event 110210) | loose | job_count 309 matches neither a component row nor the notice total 4; row date equals this notice's earliest published effective date; stored name 'Southwest Key Programs, Inc. (Casa Quetzal)' differs from the published 'Southwest Key Programs, Inc. La Esperanza)' |
| 78 | TX | [Southwest Key Programs, Inc. La Esperanza)](#78-tx-southwest-key-programs--inc--la-esperanza) 2025-08-06 | 4 | `137374` (event 110209) | loose | job_count 223 matches neither a component row nor the notice total 4; row date equals this notice's earliest published effective date; stored name 'Southwest Key Programs, Inc. (Casa Sunzal)' differs from the published 'Southwest Key Programs, Inc. La Esperanza)' |
| 78 | TX | [Southwest Key Programs, Inc. La Esperanza)](#78-tx-southwest-key-programs--inc--la-esperanza) 2025-08-06 | 4 | `137373` (event 110208) | loose | job_count 128 matches neither a component row nor the notice total 4; row date equals this notice's earliest published effective date; stored name 'Southwest Key Programs, Inc. (Casa Oasis)' differs from the published 'Southwest Key Programs, Inc. La Esperanza)' |
| 78 | TX | [Southwest Key Programs, Inc. La Esperanza)](#78-tx-southwest-key-programs--inc--la-esperanza) 2025-08-06 | 4 | `137372` (event 110207) | loose | job_count 93 matches neither a component row nor the notice total 4; row date equals this notice's earliest published effective date; stored name 'Southwest Key Programs, Inc. (Casa Sueno)' differs from the published 'Southwest Key Programs, Inc. La Esperanza)' |
| 78 | TX | [Southwest Key Programs, Inc. La Esperanza)](#78-tx-southwest-key-programs--inc--la-esperanza) 2025-08-06 | 4 | `137371` (event 110206) | loose | job_count 238 matches neither a component row nor the notice total 4; row date equals this notice's earliest published effective date; stored name 'Southwest Key Programs, Inc. (Casa Montezuma)' differs from the published 'Southwest Key Programs, Inc. La Esperanza)' |
| 78 | TX | [Southwest Key Programs, Inc. La Esperanza)](#78-tx-southwest-key-programs--inc--la-esperanza) 2025-08-06 | 4 | `137369` (event 110204) | loose | job_count 9 matches neither a component row nor the notice total 4; row date equals this notice's earliest published effective date; stored name 'Southwest Key Programs, Inc.(Casa Nueva Esperanza)' differs from the published 'Southwest Key Programs, Inc. La Esperanza)' |
| 78 | TX | [Southwest Key Programs, Inc. La Esperanza)](#78-tx-southwest-key-programs--inc--la-esperanza) 2025-08-06 | 4 | `137368` (event 110203) | loose | job_count 13 matches neither a component row nor the notice total 4; row date equals this notice's earliest published effective date; stored name 'Southwest Key Programs, Inc.(South Texas HQ)' differs from the published 'Southwest Key Programs, Inc. La Esperanza)' |
| 78 | TX | [Southwest Key Programs, Inc. La Esperanza)](#78-tx-southwest-key-programs--inc--la-esperanza) 2025-08-06 | 4 | `137367` (event 110202) | loose | job_count 1 matches neither a component row nor the notice total 4; row date equals this notice's earliest published effective date; stored name 'Southwest Key Programs, Inc. (Casa Franklin)' differs from the published 'Southwest Key Programs, Inc. La Esperanza)' |
| 78 | TX | [Southwest Key Programs, Inc. La Esperanza)](#78-tx-southwest-key-programs--inc--la-esperanza) 2025-08-06 | 4 | `137366` (event 110201) | loose | job_count 3 matches neither a component row nor the notice total 4; row date equals this notice's earliest published effective date; stored name 'Southwest Key Programs, Inc. (Casa Norma Linda)' differs from the published 'Southwest Key Programs, Inc. La Esperanza)' |
| 78 | TX | [Southwest Key Programs, Inc. La Esperanza)](#78-tx-southwest-key-programs--inc--la-esperanza) 2025-08-06 | 4 | `137365` (event 110200) | loose | job_count 3 matches neither a component row nor the notice total 4; row date equals this notice's earliest published effective date; stored name 'Southwest Key Programs, Inc. (Casa Rio Grande)' differs from the published 'Southwest Key Programs, Inc. La Esperanza)' |
| 78 | TX | [Southwest Key Programs, Inc. La Esperanza)](#78-tx-southwest-key-programs--inc--la-esperanza) 2025-08-06 | 4 | `137364` (event 110199) | loose | job_count 3 matches neither a component row nor the notice total 4; row date equals this notice's earliest published effective date; stored name 'Southwest Key Programs, Inc. (Casa Canutillo)' differs from the published 'Southwest Key Programs, Inc. La Esperanza)' |
| 78 | TX | [Southwest Key Programs, Inc. La Esperanza)](#78-tx-southwest-key-programs--inc--la-esperanza) 2025-08-06 | 4 | `137359` (event 110194) | loose | job_count 45 matches neither a component row nor the notice total 4; row date is 61 day(s) after the notice date; stored name 'Southwest Key Programs, Inc. (SWK National Headquarters)' differs from the published 'Southwest Key Programs, Inc. La Esperanza)' |
| 78 | TX | [Southwest Key Programs, Inc. La Esperanza)](#78-tx-southwest-key-programs--inc--la-esperanza) 2025-08-06 | 4 | `137093` (event 109928) | loose | job_count 2 matches neither a component row nor the notice total 4; row date is 91 day(s) after the notice date; stored name 'Southwest Key Programs-Casa Canutillo' differs from the published 'Southwest Key Programs, Inc. La Esperanza)' |
| 78 | TX | [Southwest Key Programs, Inc. La Esperanza)](#78-tx-southwest-key-programs--inc--la-esperanza) 2025-08-06 | 4 | `137092` (event 109927) | loose | job_count 5 matches neither a component row nor the notice total 4; row date is 91 day(s) after the notice date; stored name 'Southwest Key Programs-Casita Del Valle' differs from the published 'Southwest Key Programs, Inc. La Esperanza)' |
| 78 | TX | [Southwest Key Programs, Inc. La Esperanza)](#78-tx-southwest-key-programs--inc--la-esperanza) 2025-08-06 | 4 | `137091` (event 109926) | loose | job_count 1 matches neither a component row nor the notice total 4; row date is 91 day(s) after the notice date; stored name 'Southwest Key Programs-Casa Houston Reliant' differs from the published 'Southwest Key Programs, Inc. La Esperanza)' |
| 78 | TX | [Southwest Key Programs, Inc. La Esperanza)](#78-tx-southwest-key-programs--inc--la-esperanza) 2025-08-06 | 4 | `137090` (event 109925) | loose | job_count 1 matches neither a component row nor the notice total 4; row date is 91 day(s) after the notice date; stored name 'Southwest Key Programs-Casa Montezuma' differs from the published 'Southwest Key Programs, Inc. La Esperanza)' |
| 78 | TX | [Southwest Key Programs, Inc. La Esperanza)](#78-tx-southwest-key-programs--inc--la-esperanza) 2025-08-06 | 4 | `137089` (event 109924) | loose | job_count 3 matches neither a component row nor the notice total 4; row date is 91 day(s) after the notice date; stored name 'Southwest Key Programs-Casa Norma Linda' differs from the published 'Southwest Key Programs, Inc. La Esperanza)' |
| 78 | TX | [Southwest Key Programs, Inc. La Esperanza)](#78-tx-southwest-key-programs--inc--la-esperanza) 2025-08-06 | 4 | `137088` (event 109923) | loose | job_count 8 matches neither a component row nor the notice total 4; row date is 91 day(s) after the notice date; stored name 'Southwest Key Programs-Casa Nueva Esperanza' differs from the published 'Southwest Key Programs, Inc. La Esperanza)' |
| 78 | TX | [Southwest Key Programs, Inc. La Esperanza)](#78-tx-southwest-key-programs--inc--la-esperanza) 2025-08-06 | 4 | `137087` (event 109922) | loose | job_count 3 matches neither a component row nor the notice total 4; row date is 91 day(s) after the notice date; stored name 'Southwest Key Programs-Casa Rio Grande' differs from the published 'Southwest Key Programs, Inc. La Esperanza)' |
| 78 | TX | [Southwest Key Programs, Inc. La Esperanza)](#78-tx-southwest-key-programs--inc--la-esperanza) 2025-08-06 | 4 | `137086` (event 109921) | loose | job_count 3 matches neither a component row nor the notice total 4; row date is 91 day(s) after the notice date; stored name 'Southwest Key Programs-National Headquarters (Austin)' differs from the published 'Southwest Key Programs, Inc. La Esperanza)' |
| 78 | TX | [Southwest Key Programs, Inc. La Esperanza)](#78-tx-southwest-key-programs--inc--la-esperanza) 2025-08-06 | 4 | `137085` (event 109920) | loose | job_count 12 matches neither a component row nor the notice total 4; row date is 91 day(s) after the notice date; stored name 'Southwest Key Programs-STX Regional Headquarters' differs from the published 'Southwest Key Programs, Inc. La Esperanza)' |
| 78 | TX | [Southwest Key Programs, Inc. La Esperanza)](#78-tx-southwest-key-programs--inc--la-esperanza) 2025-08-06 | 4 | `137084` (event 109919) | loose | job_count 10 matches neither a component row nor the notice total 4; row date is 91 day(s) after the notice date; stored name 'Southwest Key Programs-Houston Headquarters' differs from the published 'Southwest Key Programs, Inc. La Esperanza)' |
| 79 | TX | [Condair Operations, LLC](#79-tx-condair-operations--llc) 2025-09-03 | 51 | `137117` (event 109952) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 80 | TX | [Cottonwood Creek Healthcare Community](#80-tx-cottonwood-creek-healthcare-community) 2025-09-24 | 70 | `136854` (event 109689) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 81 | TX | [Holiday Inn Club Vacations Incorporated-The ](#81-tx-holiday-inn-club-vacations-incorporated-the-villag) 2025-09-30 | 82 | `136909` (event 109744) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 82 | TX | [Southwest Key Programs-Casa Canutillo](#82-tx-southwest-key-programs-casa-canutillo) 2025-10-02 | 18 | `137093` (event 109928) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 82 | TX | [Southwest Key Programs-Casa Canutillo](#82-tx-southwest-key-programs-casa-canutillo) 2025-10-02 | 18 | `137367` (event 110202) | exact | job_count equals one published component row of this notice; row date is 3 day(s) after the notice date; stored name 'Southwest Key Programs, Inc. (Casa Franklin)' differs from the published 'Southwest Key Programs-Casa Canutillo' |
| 82 | TX | [Southwest Key Programs-Casa Canutillo](#82-tx-southwest-key-programs-casa-canutillo) 2025-10-02 | 18 | `137366` (event 110201) | exact | job_count equals one published component row of this notice; row date is 3 day(s) after the notice date; stored name 'Southwest Key Programs, Inc. (Casa Norma Linda)' differs from the published 'Southwest Key Programs-Casa Canutillo' |
| 82 | TX | [Southwest Key Programs-Casa Canutillo](#82-tx-southwest-key-programs-casa-canutillo) 2025-10-02 | 18 | `137365` (event 110200) | exact | job_count equals one published component row of this notice; row date is 3 day(s) after the notice date; stored name 'Southwest Key Programs, Inc. (Casa Rio Grande)' differs from the published 'Southwest Key Programs-Casa Canutillo' |
| 82 | TX | [Southwest Key Programs-Casa Canutillo](#82-tx-southwest-key-programs-casa-canutillo) 2025-10-02 | 18 | `137364` (event 110199) | exact | job_count equals one published component row of this notice; row date is 3 day(s) after the notice date; stored name 'Southwest Key Programs, Inc. (Casa Canutillo)' differs from the published 'Southwest Key Programs-Casa Canutillo' |
| 82 | TX | [Southwest Key Programs-Casa Canutillo](#82-tx-southwest-key-programs-casa-canutillo) 2025-10-02 | 18 | `137091` (event 109926) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Southwest Key Programs-Casa Houston Reliant' differs from the published 'Southwest Key Programs-Casa Canutillo' |
| 82 | TX | [Southwest Key Programs-Casa Canutillo](#82-tx-southwest-key-programs-casa-canutillo) 2025-10-02 | 18 | `137090` (event 109925) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Southwest Key Programs-Casa Montezuma' differs from the published 'Southwest Key Programs-Casa Canutillo' |
| 82 | TX | [Southwest Key Programs-Casa Canutillo](#82-tx-southwest-key-programs-casa-canutillo) 2025-10-02 | 18 | `137089` (event 109924) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Southwest Key Programs-Casa Norma Linda' differs from the published 'Southwest Key Programs-Casa Canutillo' |
| 82 | TX | [Southwest Key Programs-Casa Canutillo](#82-tx-southwest-key-programs-casa-canutillo) 2025-10-02 | 18 | `137088` (event 109923) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Southwest Key Programs-Casa Nueva Esperanza' differs from the published 'Southwest Key Programs-Casa Canutillo' |
| 82 | TX | [Southwest Key Programs-Casa Canutillo](#82-tx-southwest-key-programs-casa-canutillo) 2025-10-02 | 18 | `137087` (event 109922) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Southwest Key Programs-Casa Rio Grande' differs from the published 'Southwest Key Programs-Casa Canutillo' |
| 82 | TX | [Southwest Key Programs-Casa Canutillo](#82-tx-southwest-key-programs-casa-canutillo) 2025-10-02 | 18 | `137086` (event 109921) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Southwest Key Programs-National Headquarters (Austin)' differs from the published 'Southwest Key Programs-Casa Canutillo' |
| 82 | TX | [Southwest Key Programs-Casa Canutillo](#82-tx-southwest-key-programs-casa-canutillo) 2025-10-02 | 18 | `137377` (event 110212) | loose | job_count 211 matches neither a component row nor the notice total 18; row date is 3 day(s) after the notice date; stored name 'Southwest Key Programs, Inc. (Casa Houston Reliant)' differs from the published 'Southwest Key Programs-Casa Canutillo' |
| 82 | TX | [Southwest Key Programs-Casa Canutillo](#82-tx-southwest-key-programs-casa-canutillo) 2025-10-02 | 18 | `137376` (event 110211) | loose | job_count 11 matches neither a component row nor the notice total 18; row date is 3 day(s) after the notice date; stored name 'Southwest Key Programs, Inc. (Houston HQ)' differs from the published 'Southwest Key Programs-Casa Canutillo' |
| 82 | TX | [Southwest Key Programs-Casa Canutillo](#82-tx-southwest-key-programs-casa-canutillo) 2025-10-02 | 18 | `137375` (event 110210) | loose | job_count 309 matches neither a component row nor the notice total 18; row date is 3 day(s) after the notice date; stored name 'Southwest Key Programs, Inc. (Casa Quetzal)' differs from the published 'Southwest Key Programs-Casa Canutillo' |
| 82 | TX | [Southwest Key Programs-Casa Canutillo](#82-tx-southwest-key-programs-casa-canutillo) 2025-10-02 | 18 | `137374` (event 110209) | loose | job_count 223 matches neither a component row nor the notice total 18; row date is 3 day(s) after the notice date; stored name 'Southwest Key Programs, Inc. (Casa Sunzal)' differs from the published 'Southwest Key Programs-Casa Canutillo' |
| 82 | TX | [Southwest Key Programs-Casa Canutillo](#82-tx-southwest-key-programs-casa-canutillo) 2025-10-02 | 18 | `137373` (event 110208) | loose | job_count 128 matches neither a component row nor the notice total 18; row date is 3 day(s) after the notice date; stored name 'Southwest Key Programs, Inc. (Casa Oasis)' differs from the published 'Southwest Key Programs-Casa Canutillo' |
| 82 | TX | [Southwest Key Programs-Casa Canutillo](#82-tx-southwest-key-programs-casa-canutillo) 2025-10-02 | 18 | `137372` (event 110207) | loose | job_count 93 matches neither a component row nor the notice total 18; row date is 3 day(s) after the notice date; stored name 'Southwest Key Programs, Inc. (Casa Sueno)' differs from the published 'Southwest Key Programs-Casa Canutillo' |
| 82 | TX | [Southwest Key Programs-Casa Canutillo](#82-tx-southwest-key-programs-casa-canutillo) 2025-10-02 | 18 | `137371` (event 110206) | loose | job_count 238 matches neither a component row nor the notice total 18; row date is 3 day(s) after the notice date; stored name 'Southwest Key Programs, Inc. (Casa Montezuma)' differs from the published 'Southwest Key Programs-Casa Canutillo' |
| 82 | TX | [Southwest Key Programs-Casa Canutillo](#82-tx-southwest-key-programs-casa-canutillo) 2025-10-02 | 18 | `137370` (event 110205) | loose | job_count 4 matches neither a component row nor the notice total 18; row date is 3 day(s) after the notice date; stored name 'Southwest Key Programs, Inc. La Esperanza)' differs from the published 'Southwest Key Programs-Casa Canutillo' |
| 82 | TX | [Southwest Key Programs-Casa Canutillo](#82-tx-southwest-key-programs-casa-canutillo) 2025-10-02 | 18 | `137369` (event 110204) | loose | job_count 9 matches neither a component row nor the notice total 18; row date is 3 day(s) after the notice date; stored name 'Southwest Key Programs, Inc.(Casa Nueva Esperanza)' differs from the published 'Southwest Key Programs-Casa Canutillo' |
| 82 | TX | [Southwest Key Programs-Casa Canutillo](#82-tx-southwest-key-programs-casa-canutillo) 2025-10-02 | 18 | `137368` (event 110203) | loose | job_count 13 matches neither a component row nor the notice total 18; row date is 3 day(s) after the notice date; stored name 'Southwest Key Programs, Inc.(South Texas HQ)' differs from the published 'Southwest Key Programs-Casa Canutillo' |
| 82 | TX | [Southwest Key Programs-Casa Canutillo](#82-tx-southwest-key-programs-casa-canutillo) 2025-10-02 | 18 | `137359` (event 110194) | loose | job_count 45 matches neither a component row nor the notice total 18; row date is 4 day(s) after the notice date; stored name 'Southwest Key Programs, Inc. (SWK National Headquarters)' differs from the published 'Southwest Key Programs-Casa Canutillo' |
| 82 | TX | [Southwest Key Programs-Casa Canutillo](#82-tx-southwest-key-programs-casa-canutillo) 2025-10-02 | 18 | `137092` (event 109927) | loose | job_count 5 matches neither a component row nor the notice total 18; row date equals this notice's earliest published effective date; stored name 'Southwest Key Programs-Casita Del Valle' differs from the published 'Southwest Key Programs-Casa Canutillo' |
| 82 | TX | [Southwest Key Programs-Casa Canutillo](#82-tx-southwest-key-programs-casa-canutillo) 2025-10-02 | 18 | `137085` (event 109920) | loose | job_count 12 matches neither a component row nor the notice total 18; row date equals this notice's earliest published effective date; stored name 'Southwest Key Programs-STX Regional Headquarters' differs from the published 'Southwest Key Programs-Casa Canutillo' |
| 82 | TX | [Southwest Key Programs-Casa Canutillo](#82-tx-southwest-key-programs-casa-canutillo) 2025-10-02 | 18 | `137084` (event 109919) | loose | job_count 10 matches neither a component row nor the notice total 18; row date equals this notice's earliest published effective date; stored name 'Southwest Key Programs-Houston Headquarters' differs from the published 'Southwest Key Programs-Casa Canutillo' |
| 83 | TX | [Meadow Burke, LLC d/b/a Leviat](#83-tx-meadow-burke--llc-d-b-a-leviat) 2025-10-08 | 75 | `136835` (event 109670) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 84 | TX | [Job1 USA (San Antonio)](#84-tx-job1-usa--san-antonio) 2025-10-23 | 31 | `136988` (event 109823) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 84 | TX | [Job1 USA (San Antonio)](#84-tx-job1-usa--san-antonio) 2025-10-23 | 31 | `136987` (event 109822) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Job1 USA (Houston)' differs from the published 'Job1 USA (San Antonio)' |
| 84 | TX | [Job1 USA (San Antonio)](#84-tx-job1-usa--san-antonio) 2025-10-23 | 31 | `136986` (event 109821) | exact | job_count equals the summed notice total; row date equals this notice's earliest published effective date; stored name 'Job1 USA (Arlington)' differs from the published 'Job1 USA (San Antonio)' |
| 84 | TX | [Job1 USA (San Antonio)](#84-tx-job1-usa--san-antonio) 2025-10-23 | 31 | `136985` (event 109820) | loose | job_count 25 matches neither a component row nor the notice total 31; row date equals this notice's earliest published effective date; stored name 'Job1 USA (Fort Worth)' differs from the published 'Job1 USA (San Antonio)' |
| 84 | TX | [Job1 USA (San Antonio)](#84-tx-job1-usa--san-antonio) 2025-10-23 | 31 | `136984` (event 109819) | loose | job_count 25 matches neither a component row nor the notice total 31; row date equals this notice's earliest published effective date; stored name 'Job1 USA (Haslet)' differs from the published 'Job1 USA (San Antonio)' |
| 85 | TX | [Wells Fargo & Co. (Lubbock)](#85-tx-wells-fargo---co---lubbock) 2025-10-29 | 225 | `137220` (event 110055) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 86 | TX | [Apogee Architectural Metals](#86-tx-apogee-architectural-metals) 2025-11-05 | 58 | `136482` (event 109317) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 87 | TX | [FedEx Supply Chain Logistics & Electrronics,](#87-tx-fedex-supply-chain-logistics---electrronics--inc) 2025-11-25 | 856 | `136269` (event 109104) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 88 | TX | [Tyson Foods, Inc. (Amarillo B-Shift Operatio](#88-tx-tyson-foods--inc---amarillo-b-shift-operations) 2025-11-26 | 1,761 | `136371` (event 109206) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 88 | TX | [Tyson Foods, Inc. (Amarillo B-Shift Operatio](#88-tx-tyson-foods--inc---amarillo-b-shift-operations) 2025-11-26 | 1,761 | `136079` (event 108914) | exact | job_count equals one published component row of this notice; row date is 90 day(s) after the notice date; stored name 'Tyson Foods, Inc (Amarillo B-Shift Operations) Updated' differs from the published 'Tyson Foods, Inc. (Amarillo B-Shift Operations' |
| 89 | TX | [Yang Ming (America) Corporation Updated](#89-tx-yang-ming--america--corporation-updated) 2025-12-02 | 105 | `136887` (event 109722) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 90 | TX | [Telvista, Inc.](#90-tx-telvista--inc) 2025-12-26 | 110 | `136034` (event 108869) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 91 | TX | [Tyson Foods, Inc (Amarillo B-Shift Operation](#91-tx-tyson-foods--inc--amarillo-b-shift-operations--upd) 2026-01-20 | 1,761 | `136079` (event 108914) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 91 | TX | [Tyson Foods, Inc (Amarillo B-Shift Operation](#91-tx-tyson-foods--inc--amarillo-b-shift-operations--upd) 2026-01-20 | 1,761 | `136371` (event 109206) | exact | job_count equals one published component row of this notice; row date is 0 day(s) after the notice date; stored name 'Tyson Foods, Inc. (Amarillo B-Shift Operations' differs from the published 'Tyson Foods, Inc (Amarillo B-Shift Operations) Updated' |
| 92 | TX | [Compass Connections](#92-tx-compass-connections) 2026-01-29 | 148 | `135789` (event 108624) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 93 | TX | [HGS Solutions](#93-tx-hgs-solutions) 2026-02-04 | 92 | `135758` (event 108593) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 94 | TX | [Stockyards Hotel and H3 Ranch](#94-tx-stockyards-hotel-and-h3-ranch) 2026-02-19 | 120 | `135636` (event 108471) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 95 | TX | [First Brands Group, LLC(Billy Mitchell)](#95-tx-first-brands-group--llc-billy-mitchell) 2026-03-04 | 571 | `135329` (event 108164) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 95 | TX | [First Brands Group, LLC(Billy Mitchell)](#95-tx-first-brands-group--llc-billy-mitchell) 2026-03-04 | 571 | `135328` (event 108163) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'First Brands Group, LLC. (Titan Dist. Center)' differs from the published 'First Brands Group, LLC(Billy Mitchell)' |
| 95 | TX | [First Brands Group, LLC(Billy Mitchell)](#95-tx-first-brands-group--llc-billy-mitchell) 2026-03-04 | 571 | `135327` (event 108162) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'First Brands Group LLC. (ASC Facility)' differs from the published 'First Brands Group, LLC(Billy Mitchell)' |
| 96 | TX | [Albertsons #4286 (W. Freeway)](#96-tx-albertsons--4286--w--freeway) 2026-03-25 | 56 | `135435` (event 108270) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 97 | TX | [DSV Contract Logistics (3PL Logistics Facili](#97-tx-dsv-contract-logistics--3pl-logistics-facility) 2026-04-02 | 391 | `135326` (event 108161) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 98 | TX | [National Safety Apparel, LLC](#98-tx-national-safety-apparel--llc) 2026-04-23 | 50 | `134623` (event 107458) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 99 | TX | [Republic National Distributing Company, LLC ](#99-tx-republic-national-distributing-company--llc--reyes) 2026-04-23 | 1,903 | `134749` (event 107584) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 99 | TX | [Republic National Distributing Company, LLC ](#99-tx-republic-national-distributing-company--llc--reyes) 2026-04-23 | 1,903 | `134748` (event 107583) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Republic National Distributing Company, LLC (Reyes Holdings, L.L.C) Corpus Christie' differs from the published 'Republic National Distributing Company, LLC (Reyes Holdings, L.L.C) Austin' |
| 99 | TX | [Republic National Distributing Company, LLC ](#99-tx-republic-national-distributing-company--llc--reyes) 2026-04-23 | 1,903 | `134747` (event 107582) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Republic National Distributing Company, LLC (Reyes Holdings, L.L.C) Grand Prairie' differs from the published 'Republic National Distributing Company, LLC (Reyes Holdings, L.L.C) Austin' |
| 99 | TX | [Republic National Distributing Company, LLC ](#99-tx-republic-national-distributing-company--llc--reyes) 2026-04-23 | 1,903 | `134746` (event 107581) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Republic National Distributing Company, LLC (Reyes Holdings, L.L.C) Houston' differs from the published 'Republic National Distributing Company, LLC (Reyes Holdings, L.L.C) Austin' |
| 99 | TX | [Republic National Distributing Company, LLC ](#99-tx-republic-national-distributing-company--llc--reyes) 2026-04-23 | 1,903 | `134745` (event 107580) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Republic National Distributing Company, LLC (Reyes Holdings, L.L.C) San Antonio' differs from the published 'Republic National Distributing Company, LLC (Reyes Holdings, L.L.C) Austin' |
| 100 | TX | [Laurel Ridge Treatment Center (Laurel Ridge)](#100-tx-laurel-ridge-treatment-center--laurel-ridge) 2026-04-27 | 648 | `134698` (event 107533) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 101 | TX | [Spirit Airlines (IAH) May 2026](#101-tx-spirit-airlines--iah--may-2026) 2026-05-02 | 515 | `135253` (event 108088) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date |
| 101 | TX | [Spirit Airlines (IAH) May 2026](#101-tx-spirit-airlines--iah--may-2026) 2026-05-02 | 515 | `135252` (event 108087) | loose | job_count 444 matches neither a component row nor the notice total 515; row date equals this notice's earliest published effective date; stored name 'Spirit Airlines (DFW) May 2026' differs from the published 'Spirit Airlines (IAH) May 2026' |
| 102 | FL | [QB Intermediate Holdings, LLC, Quality Built](#102-fl-qb-intermediate-holdings--llc--quality-built--llc) 2025-07-07 | 70 | `138283` (event 111118) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'QB Intermediate Holdings, LLC, Quality Built, LLC, Foresite Technology Solutions, LLC (f/k/a QB Technology Co., LLC), SMC Systems LLC (d/b/a SkyeTec), SkyeTec Engineering Services, LLC, and DuctTesters, Inc.' differs from the published 'QB Intermediate Holdings, LLC, Quality Built, LLC, Foresite Technology Solutions, LLC (f/k/a QB Technology Co., LLC), SMC Systems LLC (d/b/a SkyeTec), SkyeTec Engineering Services, LLC, and DuctTesters, Inc. 9570 Regency Square Blvd Suite 410 JACKSONVILLE, FL, 32225' |
| 102 | FL | [QB Intermediate Holdings, LLC, Quality Built](#102-fl-qb-intermediate-holdings--llc--quality-built--llc) 2025-07-07 | 70 | `138282` (event 111117) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'QB Intermediate Holdings, LLC, Quality Built, LLC, Foresite Technology Solutions, LLC (f/k/a QB Technology Co., LLC), SMC Systems LLC (d/b/a SkyeTec), SkyeTec Engineering Services, LLC, and DuctTesters, Inc.' differs from the published 'QB Intermediate Holdings, LLC, Quality Built, LLC, Foresite Technology Solutions, LLC (f/k/a QB Technology Co., LLC), SMC Systems LLC (d/b/a SkyeTec), SkyeTec Engineering Services, LLC, and DuctTesters, Inc. 9570 Regency Square Blvd Suite 410 JACKSONVILLE, FL, 32225' |
| 103 | FL | [Carroll Fulmer Logistics Corporation 8340 Am](#103-fl-carroll-fulmer-logistics-corporation-8340-american) 2025-07-29 | 330 | `137541` (event 110376) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Carroll Fulmer Logistics Corporation' differs from the published 'Carroll Fulmer Logistics Corporation 8340 American Way GROVELAND, FL, 34736' |
| 104 | FL | [Pasa Services, Inc. d/b/a Flamingo Graphics ](#104-fl-pasa-services--inc--d-b-a-flamingo-graphics-13015) 2025-08-08 | 36 | `137329` (event 110164) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Pasa Services, Inc. d/b/a Flamingo Graphics' differs from the published 'Pasa Services, Inc. d/b/a Flamingo Graphics 13015 NW 38th Avenue OPA LOCKA, FL, 33054' |
| 105 | FL | [Tata Consultancy Services, Ltd 550 Water Str](#105-fl-tata-consultancy-services--ltd-550-water-street-ja) 2025-08-19 | 58 | `137279` (event 110114) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Tata Consultancy Services, Ltd' differs from the published 'Tata Consultancy Services, Ltd 550 Water Street JACKSONVILLE, FL, 32202' |
| 106 | FL | [Essendant 2405 Commerce Park Dr ORLANDO, FL,](#106-fl-essendant-2405-commerce-park-dr-orlando--fl--32819) 2025-09-04 | 73 | `136616` (event 109451) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Essendant' differs from the published 'Essendant 2405 Commerce Park Dr ORLANDO, FL, 32819' |
| 107 | FL | [Spirit Airlines Miami International Airport ](#107-fl-spirit-airlines-miami-international-airport-locate) 2025-09-25 | 71 | `136856` (event 109691) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Miami International Airport located at 4200 NW 42nd Avenue MIAMI, FL, 33142' |
| 107 | FL | [Spirit Airlines Miami International Airport ](#107-fl-spirit-airlines-miami-international-airport-locate) 2025-09-25 | 71 | `136859` (event 109694) | loose | job_count 100 matches neither a component row nor the notice total 71; row date equals this notice's earliest published effective date; stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Miami International Airport located at 4200 NW 42nd Avenue MIAMI, FL, 33142' |
| 107 | FL | [Spirit Airlines Miami International Airport ](#107-fl-spirit-airlines-miami-international-airport-locate) 2025-09-25 | 71 | `136858` (event 109693) | loose | job_count 309 matches neither a component row nor the notice total 71; row date equals this notice's earliest published effective date; stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Miami International Airport located at 4200 NW 42nd Avenue MIAMI, FL, 33142' |
| 107 | FL | [Spirit Airlines Miami International Airport ](#107-fl-spirit-airlines-miami-international-airport-locate) 2025-09-25 | 71 | `136857` (event 109692) | loose | job_count 350 matches neither a component row nor the notice total 71; row date equals this notice's earliest published effective date; stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Miami International Airport located at 4200 NW 42nd Avenue MIAMI, FL, 33142' |
| 107 | FL | [Spirit Airlines Miami International Airport ](#107-fl-spirit-airlines-miami-international-airport-locate) 2025-09-25 | 71 | `135257` (event 108092) | loose | job_count 551 matches neither a component row nor the notice total 71; row date is 219 day(s) after the notice date; stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Miami International Airport located at 4200 NW 42nd Avenue MIAMI, FL, 33142' |
| 107 | FL | [Spirit Airlines Miami International Airport ](#107-fl-spirit-airlines-miami-international-airport-locate) 2025-09-25 | 71 | `135256` (event 108091) | loose | job_count 181 matches neither a component row nor the notice total 71; row date is 219 day(s) after the notice date; stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Miami International Airport located at 4200 NW 42nd Avenue MIAMI, FL, 33142' |
| 107 | FL | [Spirit Airlines Miami International Airport ](#107-fl-spirit-airlines-miami-international-airport-locate) 2025-09-25 | 71 | `135255` (event 108090) | loose | job_count 796 matches neither a component row nor the notice total 71; row date is 219 day(s) after the notice date; stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Miami International Airport located at 4200 NW 42nd Avenue MIAMI, FL, 33142' |
| 107 | FL | [Spirit Airlines Miami International Airport ](#107-fl-spirit-airlines-miami-international-airport-locate) 2025-09-25 | 71 | `135254` (event 108089) | loose | job_count 2529 matches neither a component row nor the notice total 71; row date is 219 day(s) after the notice date; stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Miami International Airport located at 4200 NW 42nd Avenue MIAMI, FL, 33142' |
| 107 | FL | [Spirit Airlines Miami International Airport ](#107-fl-spirit-airlines-miami-international-airport-locate) 2025-09-25 | 71 | `176452` (event 149196) | loose | row source is news/filing, not a WARN-tier row; job_count 4000 matches neither a component row nor the notice total 71; row date is 222 day(s) after the notice date; stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Miami International Airport located at 4200 NW 42nd Avenue MIAMI, FL, 33142' |
| 108 | FL | [ID Logistics 2007 Gandy Blvd. N SAINT PETERS](#108-fl-id-logistics-2007-gandy-blvd--n-saint-petersburg) 2025-10-02 | 174 | `136751` (event 109586) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'ID Logistics' differs from the published 'ID Logistics 2007 Gandy Blvd. N SAINT PETERSBURG, FL, 33702' |
| 108 | FL | [ID Logistics 2007 Gandy Blvd. N SAINT PETERS](#108-fl-id-logistics-2007-gandy-blvd--n-saint-petersburg) 2025-10-02 | 174 | `136750` (event 109585) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'ID Logistics' differs from the published 'ID Logistics 2007 Gandy Blvd. N SAINT PETERSBURG, FL, 33702' |
| 109 | FL | [Reworld Projects, LLC 3001 110th Ave. N SAIN](#109-fl-reworld-projects--llc-3001-110th-ave--n-saint-pete) 2025-10-10 | 70 | `136617` (event 109452) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Reworld Projects, LLC' differs from the published 'Reworld Projects, LLC 3001 110th Ave. N SAINT PETERSBURG, FL, 33716' |
| 110 | FL | [Eulen Aviation 2100 NW 42nd Ave MIAMI, FL, 3](#110-fl-eulen-aviation-2100-nw-42nd-ave-miami--fl--33142) 2025-10-23 | 100 | `136804` (event 109639) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Eulen Aviation' differs from the published 'Eulen Aviation 2100 NW 42nd Ave MIAMI, FL, 33142' |
| 111 | FL | [Frito-Lay, Inc 2000 Parks Oaks Avenue ORLAND](#111-fl-frito-lay--inc-2000-parks-oaks-avenue-orlando--fl) 2025-11-04 | 500 | `137101` (event 109936) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Frito-Lay, Inc' differs from the published 'Frito-Lay, Inc 2000 Parks Oaks Avenue ORLANDO, FL, 32808' |
| 111 | FL | [Frito-Lay, Inc 2000 Parks Oaks Avenue ORLAND](#111-fl-frito-lay--inc-2000-parks-oaks-avenue-orlando--fl) 2025-11-04 | 500 | `137100` (event 109935) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Frito-Lay, Inc' differs from the published 'Frito-Lay, Inc 2000 Parks Oaks Avenue ORLANDO, FL, 32808' |
| 112 | FL | [Hudson 1 Jeff Fuqua Blvd ORLANDO, FL, 32827](#112-fl-hudson-1-jeff-fuqua-blvd-orlando--fl--32827) 2025-11-18 | 133 | `136359` (event 109194) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Hudson' differs from the published 'Hudson 1 Jeff Fuqua Blvd ORLANDO, FL, 32827' |
| 112 | FL | [Hudson 1 Jeff Fuqua Blvd ORLANDO, FL, 32827](#112-fl-hudson-1-jeff-fuqua-blvd-orlando--fl--32827) 2025-11-18 | 133 | `136659` (event 109494) | loose | job_count 14 matches neither a component row nor the notice total 133; row date is 40 day(s) after the notice date; stored name 'Hudson' differs from the published 'Hudson 1 Jeff Fuqua Blvd ORLANDO, FL, 32827' |
| 113 | FL | [Kroger Fulfillment Network LLC Kroger Tampa ](#113-fl-kroger-fulfillment-network-llc-kroger-tampa-fulfil) 2025-11-18 | 1,350 | `136219` (event 109054) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Kroger Fulfillment Network LLC' differs from the published 'Kroger Fulfillment Network LLC Kroger Tampa Fulfillment Center, 1820 Massaro Blvd TAMPA, FL, 33619' |
| 113 | FL | [Kroger Fulfillment Network LLC Kroger Tampa ](#113-fl-kroger-fulfillment-network-llc-kroger-tampa-fulfil) 2025-11-18 | 1,350 | `136218` (event 109053) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Kroger Fulfillment Network LLC' differs from the published 'Kroger Fulfillment Network LLC Kroger Tampa Fulfillment Center, 1820 Massaro Blvd TAMPA, FL, 33619' |
| 113 | FL | [Kroger Fulfillment Network LLC Kroger Tampa ](#113-fl-kroger-fulfillment-network-llc-kroger-tampa-fulfil) 2025-11-18 | 1,350 | `136217` (event 109052) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Kroger Fulfillment Network LLC' differs from the published 'Kroger Fulfillment Network LLC Kroger Tampa Fulfillment Center, 1820 Massaro Blvd TAMPA, FL, 33619' |
| 113 | FL | [Kroger Fulfillment Network LLC Kroger Tampa ](#113-fl-kroger-fulfillment-network-llc-kroger-tampa-fulfil) 2025-11-18 | 1,350 | `136216` (event 109051) | loose | job_count 53 matches neither a component row nor the notice total 1350; row date equals this notice's earliest published effective date; stored name 'Kroger Fulfillment Network LLC' differs from the published 'Kroger Fulfillment Network LLC Kroger Tampa Fulfillment Center, 1820 Massaro Blvd TAMPA, FL, 33619' |
| 114 | FL | [Sodexo, Inc and Affiliates Miami Jewish Heal](#114-fl-sodexo--inc-and-affiliates-miami-jewish-health-520) 2025-11-22 | 163 | `136035` (event 108870) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Sodexo, Inc and Affiliates' differs from the published 'Sodexo, Inc and Affiliates Miami Jewish Health 5200 NE 2nd Ave MIAMI, FL, 33137' |
| 115 | FL | [Railcrew Xpress 1718-1 North McDuff Avenue J](#115-fl-railcrew-xpress-1718-1-north-mcduff-avenue-jackson) 2025-12-22 | 79 | `136058` (event 108893) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Railcrew Xpress' differs from the published 'Railcrew Xpress 1718-1 North McDuff Avenue JACKSONVILLE, FL, 32254' |
| 115 | FL | [Railcrew Xpress 1718-1 North McDuff Avenue J](#115-fl-railcrew-xpress-1718-1-north-mcduff-avenue-jackson) 2025-12-22 | 79 | `136057` (event 108892) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Railcrew Xpress' differs from the published 'Railcrew Xpress 1718-1 North McDuff Avenue JACKSONVILLE, FL, 32254' |
| 115 | FL | [Railcrew Xpress 1718-1 North McDuff Avenue J](#115-fl-railcrew-xpress-1718-1-north-mcduff-avenue-jackson) 2025-12-22 | 79 | `136056` (event 108891) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Railcrew Xpress' differs from the published 'Railcrew Xpress 1718-1 North McDuff Avenue JACKSONVILLE, FL, 32254' |
| 115 | FL | [Railcrew Xpress 1718-1 North McDuff Avenue J](#115-fl-railcrew-xpress-1718-1-north-mcduff-avenue-jackson) 2025-12-22 | 79 | `136055` (event 108890) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Railcrew Xpress' differs from the published 'Railcrew Xpress 1718-1 North McDuff Avenue JACKSONVILLE, FL, 32254' |
| 115 | FL | [Railcrew Xpress 1718-1 North McDuff Avenue J](#115-fl-railcrew-xpress-1718-1-north-mcduff-avenue-jackson) 2025-12-22 | 79 | `136054` (event 108889) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Railcrew Xpress' differs from the published 'Railcrew Xpress 1718-1 North McDuff Avenue JACKSONVILLE, FL, 32254' |
| 116 | FL | [SMBC MANUBANK Bradenton 515 South Figueroa S](#116-fl-smbc-manubank-bradenton-515-south-figueroa-street) 2026-01-08 | 1 | `135930` (event 108765) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'SMBC MANUBANK' differs from the published 'SMBC MANUBANK Bradenton 515 South Figueroa Street Los Angeles, CA 90071 BRADENTON, FL, 34207' |
| 116 | FL | [SMBC MANUBANK Bradenton 515 South Figueroa S](#116-fl-smbc-manubank-bradenton-515-south-figueroa-street) 2026-01-08 | 1 | `135931` (event 108766) | loose | job_count 4 matches neither a component row nor the notice total 1; row date equals this notice's earliest published effective date; stored name 'SMBC MANUBANK' differs from the published 'SMBC MANUBANK Bradenton 515 South Figueroa Street Los Angeles, CA 90071 BRADENTON, FL, 34207' |
| 117 | FL | [SMBC MANUBANK Marco Island 515 South Figuero](#117-fl-smbc-manubank-marco-island-515-south-figueroa-stre) 2026-01-08 | 1 | `135930` (event 108765) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'SMBC MANUBANK' differs from the published 'SMBC MANUBANK Marco Island 515 South Figueroa Street Los Angeles, CA 90071 MARCO ISLAND, FL, 34145' |
| 117 | FL | [SMBC MANUBANK Marco Island 515 South Figuero](#117-fl-smbc-manubank-marco-island-515-south-figueroa-stre) 2026-01-08 | 1 | `135931` (event 108766) | loose | job_count 4 matches neither a component row nor the notice total 1; row date equals this notice's earliest published effective date; stored name 'SMBC MANUBANK' differs from the published 'SMBC MANUBANK Marco Island 515 South Figueroa Street Los Angeles, CA 90071 MARCO ISLAND, FL, 34145' |
| 118 | FL | [Host International, Inc. 1 Jeff Fuqua Blvd O](#118-fl-host-international--inc--1-jeff-fuqua-blvd-orlando) 2026-01-16 | 92 | `136261` (event 109096) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Host International, Inc.' differs from the published 'Host International, Inc. 1 Jeff Fuqua Blvd ORLANDO, FL, 32827' |
| 119 | FL | [Saks & Company LLC 2784 Executive Way MIRAMA](#119-fl-saks---company-llc-2784-executive-way-miramar--fl) 2026-01-23 | 74 | `135803` (event 108638) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Saks & Company LLC' differs from the published 'Saks & Company LLC 2784 Executive Way MIRAMAR, FL, 33025' |
| 119 | FL | [Saks & Company LLC 2784 Executive Way MIRAMA](#119-fl-saks---company-llc-2784-executive-way-miramar--fl) 2026-01-23 | 74 | `135291` (event 108126) | loose | job_count 66 matches neither a component row nor the notice total 74; row date is 98 day(s) after the notice date; stored name 'Saks & Company LLC' differs from the published 'Saks & Company LLC 2784 Executive Way MIRAMAR, FL, 33025' |
| 120 | FL | [Liberty Dental Plan Corporation 3109 W. Dr. ](#120-fl-liberty-dental-plan-corporation-3109-w--dr--martin) 2026-02-05 | 102 | `135638` (event 108473) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Liberty Dental Plan Corporation' differs from the published 'Liberty Dental Plan Corporation 3109 W. Dr. Martin Luther King Jr. Blvd Suite 100 TAMPA, FL, 33607' |
| 121 | FL | [TTEC 7195 34th Street South, SAINT PETERSBUR](#121-fl-ttec-7195-34th-street-south--saint-petersburg--fl) 2026-02-13 | 57 | `135555` (event 108390) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'TTEC' differs from the published 'TTEC 7195 34th Street South, SAINT PETERSBURG, FL, 33711' |
| 122 | FL | [Parsec, LLC 6098 Soutel Drive JACKSONVILLE, ](#122-fl-parsec--llc-6098-soutel-drive-jacksonville--fl--32) 2026-02-23 | 147 | `135288` (event 108123) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Parsec, LLC' differs from the published 'Parsec, LLC 6098 Soutel Drive JACKSONVILLE, FL, 32219' |
| 123 | FL | [Trulieve, Inc. 13773 Icot Blvd Bldg. 5 CLEAR](#123-fl-trulieve--inc--13773-icot-blvd-bldg--5-clear-water) 2026-03-02 | 58 | `135290` (event 108125) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Trulieve, Inc.' differs from the published 'Trulieve, Inc. 13773 Icot Blvd Bldg. 5 CLEAR WATER, FL, 33760' |
| 124 | FL | [HCL America, Inc 9002 San Marco Court ORLAND](#124-fl-hcl-america--inc-9002-san-marco-court-orlando--fl) 2026-03-27 | 120 | `135073` (event 107908) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'HCL America, Inc' differs from the published 'HCL America, Inc 9002 San Marco Court ORLANDO, FL, 32819' |
| 125 | FL | [Amazon 27505 SW 132 Ave TMB8 HOMESTEAD, FL, ](#125-fl-amazon-27505-sw-132-ave-tmb8-homestead--fl--33032) 2026-04-17 | 616 | `134509` (event 107344) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Amazon' differs from the published 'Amazon 27505 SW 132 Ave TMB8 HOMESTEAD, FL, 33032' |
| 125 | FL | [Amazon 27505 SW 132 Ave TMB8 HOMESTEAD, FL, ](#125-fl-amazon-27505-sw-132-ave-tmb8-homestead--fl--33032) 2026-04-17 | 616 | `133994` (event 106829) | loose | job_count 494 matches neither a component row nor the notice total 616; row date is 153 day(s) after the notice date; stored name 'Amazon' differs from the published 'Amazon 27505 SW 132 Ave TMB8 HOMESTEAD, FL, 33032' |
| 125 | FL | [Amazon 27505 SW 132 Ave TMB8 HOMESTEAD, FL, ](#125-fl-amazon-27505-sw-132-ave-tmb8-homestead--fl--33032) 2026-04-17 | 616 | `176659` (event 149392) | loose | row source is news/filing, not a WARN-tier row; job_count 1100 matches neither a component row nor the notice total 616; row date is 101 day(s) after the notice date; stored name 'Amazon' differs from the published 'Amazon 27505 SW 132 Ave TMB8 HOMESTEAD, FL, 33032' |
| 126 | FL | [Republic National Distributing Company 441 S](#126-fl-republic-national-distributing-company-441-sw-12-a) 2026-04-22 | 653 | `134752` (event 107587) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Republic National Distributing Company' differs from the published 'Republic National Distributing Company 441 SW 12 Ave DEERFIELD BEACH, FL, 33442' |
| 126 | FL | [Republic National Distributing Company 441 S](#126-fl-republic-national-distributing-company-441-sw-12-a) 2026-04-22 | 653 | `134751` (event 107586) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Republic National Distributing Company' differs from the published 'Republic National Distributing Company 441 SW 12 Ave DEERFIELD BEACH, FL, 33442' |
| 126 | FL | [Republic National Distributing Company 441 S](#126-fl-republic-national-distributing-company-441-sw-12-a) 2026-04-22 | 653 | `134750` (event 107585) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Republic National Distributing Company' differs from the published 'Republic National Distributing Company 441 SW 12 Ave DEERFIELD BEACH, FL, 33442' |
| 126 | FL | [Republic National Distributing Company 441 S](#126-fl-republic-national-distributing-company-441-sw-12-a) 2026-04-22 | 653 | `134753` (event 107588) | loose | job_count 393 matches neither a component row nor the notice total 653; row date equals this notice's earliest published effective date; stored name 'Republic National Distributing Company' differs from the published 'Republic National Distributing Company 441 SW 12 Ave DEERFIELD BEACH, FL, 33442' |
| 127 | FL | [Msgr. Bryan Walsh Children’s Village 9525 St](#127-fl-msgr--bryan-walsh-children-s-village-9525-sterling) 2026-04-27 | 84 | `135002` (event 107837) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Msgr. Bryan Walsh Children?s Village' differs from the published 'Msgr. Bryan Walsh Children’s Village 9525 Sterling Drive MIAMI, FL, 33157' |
| 128 | FL | [Spirit Airlines Miami International Airport ](#128-fl-spirit-airlines-miami-international-airport--mia) 2026-05-04 | 181 | `135256` (event 108091) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Miami International Airport (MIA) 2100 NW 42nd Ave, Miami MIAMI, FL, 33142' |
| 128 | FL | [Spirit Airlines Miami International Airport ](#128-fl-spirit-airlines-miami-international-airport--mia) 2026-05-04 | 181 | `135257` (event 108092) | loose | job_count 551 matches neither a component row nor the notice total 181; row date equals this notice's earliest published effective date; stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Miami International Airport (MIA) 2100 NW 42nd Ave, Miami MIAMI, FL, 33142' |
| 128 | FL | [Spirit Airlines Miami International Airport ](#128-fl-spirit-airlines-miami-international-airport--mia) 2026-05-04 | 181 | `135255` (event 108090) | loose | job_count 796 matches neither a component row nor the notice total 181; row date equals this notice's earliest published effective date; stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Miami International Airport (MIA) 2100 NW 42nd Ave, Miami MIAMI, FL, 33142' |
| 128 | FL | [Spirit Airlines Miami International Airport ](#128-fl-spirit-airlines-miami-international-airport--mia) 2026-05-04 | 181 | `135254` (event 108089) | loose | job_count 2529 matches neither a component row nor the notice total 181; row date equals this notice's earliest published effective date; stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Miami International Airport (MIA) 2100 NW 42nd Ave, Miami MIAMI, FL, 33142' |
| 128 | FL | [Spirit Airlines Miami International Airport ](#128-fl-spirit-airlines-miami-international-airport--mia) 2026-05-04 | 181 | `176452` (event 149196) | loose | row source is news/filing, not a WARN-tier row; job_count 4000 matches neither a component row nor the notice total 181; row date is 1 day(s) after the notice date; stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Miami International Airport (MIA) 2100 NW 42nd Ave, Miami MIAMI, FL, 33142' |
| 129 | FL | [Spirit Airlines Fort Lauderdale-Hollywood In](#129-fl-spirit-airlines-fort-lauderdale-hollywood-internat) 2026-05-04 | 2,529 | `135254` (event 108089) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Fort Lauderdale-Hollywood International Airport (FLL) 100 Terminal Dr, Fort Lauderdale FORT LAUDERDALE, FL, 33315' |
| 129 | FL | [Spirit Airlines Fort Lauderdale-Hollywood In](#129-fl-spirit-airlines-fort-lauderdale-hollywood-internat) 2026-05-04 | 2,529 | `135257` (event 108092) | loose | job_count 551 matches neither a component row nor the notice total 2529; row date equals this notice's earliest published effective date; stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Fort Lauderdale-Hollywood International Airport (FLL) 100 Terminal Dr, Fort Lauderdale FORT LAUDERDALE, FL, 33315' |
| 129 | FL | [Spirit Airlines Fort Lauderdale-Hollywood In](#129-fl-spirit-airlines-fort-lauderdale-hollywood-internat) 2026-05-04 | 2,529 | `135256` (event 108091) | loose | job_count 181 matches neither a component row nor the notice total 2529; row date equals this notice's earliest published effective date; stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Fort Lauderdale-Hollywood International Airport (FLL) 100 Terminal Dr, Fort Lauderdale FORT LAUDERDALE, FL, 33315' |
| 129 | FL | [Spirit Airlines Fort Lauderdale-Hollywood In](#129-fl-spirit-airlines-fort-lauderdale-hollywood-internat) 2026-05-04 | 2,529 | `135255` (event 108090) | loose | job_count 796 matches neither a component row nor the notice total 2529; row date equals this notice's earliest published effective date; stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Fort Lauderdale-Hollywood International Airport (FLL) 100 Terminal Dr, Fort Lauderdale FORT LAUDERDALE, FL, 33315' |
| 129 | FL | [Spirit Airlines Fort Lauderdale-Hollywood In](#129-fl-spirit-airlines-fort-lauderdale-hollywood-internat) 2026-05-04 | 2,529 | `176452` (event 149196) | loose | row source is news/filing, not a WARN-tier row; job_count 4000 matches neither a component row nor the notice total 2529; row date is 1 day(s) after the notice date; stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Fort Lauderdale-Hollywood International Airport (FLL) 100 Terminal Dr, Fort Lauderdale FORT LAUDERDALE, FL, 33315' |
| 130 | FL | [Spirit Airlines MCO Infight & Operations Cen](#130-fl-spirit-airlines-mco-infight---operations-center--o) 2026-05-04 | 796 | `135255` (event 108090) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Spirit Airlines' differs from the published 'Spirit Airlines MCO Infight & Operations Center (OOC) 10084 Air Tran Blvd Orlando ORLANDO, FL, 32827' |
| 130 | FL | [Spirit Airlines MCO Infight & Operations Cen](#130-fl-spirit-airlines-mco-infight---operations-center--o) 2026-05-04 | 796 | `135257` (event 108092) | loose | job_count 551 matches neither a component row nor the notice total 796; row date equals this notice's earliest published effective date; stored name 'Spirit Airlines' differs from the published 'Spirit Airlines MCO Infight & Operations Center (OOC) 10084 Air Tran Blvd Orlando ORLANDO, FL, 32827' |
| 130 | FL | [Spirit Airlines MCO Infight & Operations Cen](#130-fl-spirit-airlines-mco-infight---operations-center--o) 2026-05-04 | 796 | `135256` (event 108091) | loose | job_count 181 matches neither a component row nor the notice total 796; row date equals this notice's earliest published effective date; stored name 'Spirit Airlines' differs from the published 'Spirit Airlines MCO Infight & Operations Center (OOC) 10084 Air Tran Blvd Orlando ORLANDO, FL, 32827' |
| 130 | FL | [Spirit Airlines MCO Infight & Operations Cen](#130-fl-spirit-airlines-mco-infight---operations-center--o) 2026-05-04 | 796 | `135254` (event 108089) | loose | job_count 2529 matches neither a component row nor the notice total 796; row date equals this notice's earliest published effective date; stored name 'Spirit Airlines' differs from the published 'Spirit Airlines MCO Infight & Operations Center (OOC) 10084 Air Tran Blvd Orlando ORLANDO, FL, 32827' |
| 130 | FL | [Spirit Airlines MCO Infight & Operations Cen](#130-fl-spirit-airlines-mco-infight---operations-center--o) 2026-05-04 | 796 | `176452` (event 149196) | loose | row source is news/filing, not a WARN-tier row; job_count 4000 matches neither a component row nor the notice total 796; row date is 1 day(s) after the notice date; stored name 'Spirit Airlines' differs from the published 'Spirit Airlines MCO Infight & Operations Center (OOC) 10084 Air Tran Blvd Orlando ORLANDO, FL, 32827' |
| 131 | FL | [Spirit Airlines Orlando International Airpor](#131-fl-spirit-airlines-orlando-international-airport--mco) 2026-05-04 | 796 | `135255` (event 108090) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Orlando International Airport (MCO) 1 Jeff Fuqua Blvd, Orlando ORLANDO, FL, 32827' |
| 131 | FL | [Spirit Airlines Orlando International Airpor](#131-fl-spirit-airlines-orlando-international-airport--mco) 2026-05-04 | 796 | `135257` (event 108092) | loose | job_count 551 matches neither a component row nor the notice total 796; row date equals this notice's earliest published effective date; stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Orlando International Airport (MCO) 1 Jeff Fuqua Blvd, Orlando ORLANDO, FL, 32827' |
| 131 | FL | [Spirit Airlines Orlando International Airpor](#131-fl-spirit-airlines-orlando-international-airport--mco) 2026-05-04 | 796 | `135256` (event 108091) | loose | job_count 181 matches neither a component row nor the notice total 796; row date equals this notice's earliest published effective date; stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Orlando International Airport (MCO) 1 Jeff Fuqua Blvd, Orlando ORLANDO, FL, 32827' |
| 131 | FL | [Spirit Airlines Orlando International Airpor](#131-fl-spirit-airlines-orlando-international-airport--mco) 2026-05-04 | 796 | `135254` (event 108089) | loose | job_count 2529 matches neither a component row nor the notice total 796; row date equals this notice's earliest published effective date; stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Orlando International Airport (MCO) 1 Jeff Fuqua Blvd, Orlando ORLANDO, FL, 32827' |
| 131 | FL | [Spirit Airlines Orlando International Airpor](#131-fl-spirit-airlines-orlando-international-airport--mco) 2026-05-04 | 796 | `176452` (event 149196) | loose | row source is news/filing, not a WARN-tier row; job_count 4000 matches neither a component row nor the notice total 796; row date is 1 day(s) after the notice date; stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Orlando International Airport (MCO) 1 Jeff Fuqua Blvd, Orlando ORLANDO, FL, 32827' |
| 132 | FL | [Spirit Airlines Spirit Support Center 1731 R](#132-fl-spirit-airlines-spirit-support-center-1731-radiant) 2026-05-04 | 551 | `135257` (event 108092) | exact | job_count equals one published component row of this notice; row date equals this notice's earliest published effective date; stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Spirit Support Center 1731 Radiant Drive Dania Beach DANIA BEACH, FL, 33004' |
| 132 | FL | [Spirit Airlines Spirit Support Center 1731 R](#132-fl-spirit-airlines-spirit-support-center-1731-radiant) 2026-05-04 | 551 | `135256` (event 108091) | loose | job_count 181 matches neither a component row nor the notice total 551; row date equals this notice's earliest published effective date; stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Spirit Support Center 1731 Radiant Drive Dania Beach DANIA BEACH, FL, 33004' |
| 132 | FL | [Spirit Airlines Spirit Support Center 1731 R](#132-fl-spirit-airlines-spirit-support-center-1731-radiant) 2026-05-04 | 551 | `135255` (event 108090) | loose | job_count 796 matches neither a component row nor the notice total 551; row date equals this notice's earliest published effective date; stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Spirit Support Center 1731 Radiant Drive Dania Beach DANIA BEACH, FL, 33004' |
| 132 | FL | [Spirit Airlines Spirit Support Center 1731 R](#132-fl-spirit-airlines-spirit-support-center-1731-radiant) 2026-05-04 | 551 | `135254` (event 108089) | loose | job_count 2529 matches neither a component row nor the notice total 551; row date equals this notice's earliest published effective date; stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Spirit Support Center 1731 Radiant Drive Dania Beach DANIA BEACH, FL, 33004' |
| 132 | FL | [Spirit Airlines Spirit Support Center 1731 R](#132-fl-spirit-airlines-spirit-support-center-1731-radiant) 2026-05-04 | 551 | `176452` (event 149196) | loose | row source is news/filing, not a WARN-tier row; job_count 4000 matches neither a component row nor the notice total 551; row date is 1 day(s) after the notice date; stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Spirit Support Center 1731 Radiant Drive Dania Beach DANIA BEACH, FL, 33004' |

Recording a decision is a separate, network-free step:

```
python3 railway/warn_adjudicate.py --accept <reference_row_id> \
    --reviewed-by 'Your Name' --reason '...' --row-ids <tracker_row_id> ...
python3 railway/warn_adjudicate.py --reject <reference_row_id> \
    --reviewed-by 'Your Name' --reason '...' --row-ids <tracker_row_id> ...
```

---

## 1. Republic National Distributing Company (CA)

`warn-ca-2025-07-01-republic-national-distributing` — currently `not_matched`, stratum `large_census`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-07-01**, effective 2025-09-02..2025-09-02
- **1,364** affected across 6 published row(s)
  - Republic National Distributing Company — 104 — Alameda County; 30825 Wiegman Road  Hayward CA 94544 — `page 22, text row at y=593.2`
  - Republic National Distributing Company (14352) — 79 — Orange County; 14352 Franklin Ave  Tustin CA 92780 — `page 22, text row at y=555.4`
  - Republic National Distributing Company (14402) — 561 — Orange County; 14402 Franklin Ave  Tustin CA 92780 — `page 22, text row at y=547.8`
  - Republic National Distributing Company, LLC — 238 — San Bernardino County; 6711 Bickmore Ave  Chino CA 91710 — `page 22, text row at y=540.2`
  - Republic National Distributing Company — 226 — Alameda County; 5100 Franklin Drive  Pleasanton CA 94588 — `page 22, text row at y=487.3`
  - Republic National Distributing Company — 156 — Santa Clara County; 850 Jarvis Dr  Morgan Hill CA 95037 — `page 22, text row at y=464.6`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2025-06-01 .. 2026-08-05

**7 candidate row(s).** Each block below is one row and says nothing about any other.

### row `137738` — event `2463` — tier `exact`

- stored name: `Republic National Distributing Company`
- stored count **156**, date `2025-09-02`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Republic National Distributing Company` — 156 — 2025-09-02 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `137736` — event `2461` — tier `exact`

- stored name: `Republic National Distributing Company`
- stored count **226**, date `2025-09-02`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Republic National Distributing Company` — 226 — 2025-09-02 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `137725` — event `2450` — tier `exact`

- stored name: `Republic National Distributing Company`
- stored count **104**, date `2025-09-02`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Republic National Distributing Company` — 104 — 2025-09-02 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `137729` — event `2454` — tier `exact`

- stored name: `Republic National Distributing Company, LLC`
- stored count **238**, date `2025-09-02`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Republic National Distributing Company, LLC` — 238 — 2025-09-02 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Republic National Distributing Company, LLC' differs from the published 'Republic National Distributing Company'

### row `137728` — event `2453` — tier `exact`

- stored name: `Republic National Distributing Company (14402)`
- stored count **561**, date `2025-09-02`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Republic National Distributing Company (14402)` — 561 — 2025-09-02 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Republic National Distributing Company (14402)' differs from the published 'Republic National Distributing Company'

### row `137727` — event `2452` — tier `exact`

- stored name: `Republic National Distributing Company (14352)`
- stored count **79**, date `2025-09-02`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Republic National Distributing Company (14352)` — 79 — 2025-09-02 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Republic National Distributing Company (14352)' differs from the published 'Republic National Distributing Company'

### row `70355` — event `43695` — tier `loose`

- stored name: `Republic National`
- stored count **1756**, date `2025-09-02`, state `CA`, source `news` / `mercurynews.com`
- live now: `Republic National` — 1756 — 2025-09-02 — `news`
- our cited source: <https://www.mercurynews.com/2025/07/16/alcohol-distributor-republic-national-laying-off-1756-in-california-as-it-exits-state/>
- flags for this row:
  - row source is news/filing, not a WARN-tier row
  - job_count 1756 matches neither a component row nor the notice total 1364
  - row date equals this notice's earliest published effective date
  - stored name 'Republic National' differs from the published 'Republic National Distributing Company'

---

## 2. (1045) San Diego LGBT Community Center (CA)

`warn-ca-2025-07-03-1045-san-diego-lgbt` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-07-03**, effective 2025-09-06..2025-09-06
- **6** affected across 1 published row(s)
  - (1045) San Diego LGBT Community Center — 6 — San Diego County; 1045 11th Ave.  San Diego CA 92101 — `page 22, text row at y=245.4`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2025-06-03 .. 2026-08-07

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `137699` — event `2431` — tier `exact`

- stored name: `(1045) San Diego LGBT Community Center`
- stored count **6**, date `2025-09-06`, state `CA`, source `warn` / `CA WARN notice`
- live now: `(1045) San Diego LGBT Community Center` — 6 — 2025-09-06 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 3. Intel Corporation (Robert Noyce Building) (CA)

`warn-ca-2025-07-07-intel` — currently `not_matched`, stratum `large_census`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-07-07**, effective 2025-07-11..2025-07-15
- **584** affected across 7 published row(s)
  - Intel Corporation (Robert Noyce Building) — 184 — Santa Clara County; 2200 Mission College Boulevard  Santa Clara CA 95054 — `page 22, text row at y=404.2`
  - Intel Corporation (SC-1) — 1 — Santa Clara County; 3065 Bowers Avenue  Santa Clara CA 95054 — `page 22, text row at y=396.6`
  - Intel Corporation (SC-2) — 1 — Santa Clara County; 3065 Bowers Avenue  Santa Clara CA 95054 — `page 22, text row at y=389.0`
  - Intel Corporation (SC-9) — 37 — Santa Clara County; 3601 Juliette Lane  Santa Clara CA 95054 — `page 22, text row at y=381.5`
  - Intel Corporation (SC-11) — 8 — Santa Clara County; 2191 Laurelwood Rd  Santa Clara CA 95054 — `page 22, text row at y=373.9`
  - Intel Corporation (SC-12) — 179 — Santa Clara County; 3600 Juliette Lane  Santa Clara CA 95054 — `page 22, text row at y=366.4`
  - Intel Corporation — 174 — Sacramento County; 1900 Prairie City Rd  Folsom CA 95630 — `page 22, text row at y=343.7`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2025-06-07 .. 2026-08-11

**34 candidate row(s).** Each block below is one row and says nothing about any other.

### row `138141` — event `2657` — tier `exact`

- stored name: `Intel Corporation (Robert Noyce Building)`
- stored count **184**, date `2025-07-15`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Intel Corporation (Robert Noyce Building)` — 184 — 2025-07-15 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is 8 day(s) after the notice date

### row `136875` — event `1965` — tier `loose`

- stored name: `Intel Corporation (Robert Noyce Building)`
- stored count **45**, date `2025-11-30`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Intel Corporation (Robert Noyce Building)` — 45 — 2025-11-30 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 45 matches neither a component row nor the notice total 584
  - row date is 146 day(s) after the notice date

### row `138203` — event `2699` — tier `exact`

- stored name: `Intel Corporation`
- stored count **174**, date `2025-07-11`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Intel Corporation` — 174 — 2025-07-11 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Intel Corporation' differs from the published 'Intel Corporation (Robert Noyce Building)'

### row `138162` — event `2678` — tier `exact`

- stored name: `Intel Corporation - SC-2`
- stored count **1**, date `2025-07-15`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Intel Corporation - SC-2` — 1 — 2025-07-15 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is 8 day(s) after the notice date
  - stored name 'Intel Corporation - SC-2' differs from the published 'Intel Corporation (Robert Noyce Building)'

### row `138161` — event `2677` — tier `exact`

- stored name: `Intel Corporation - SC-1 3065 Bowers`
- stored count **1**, date `2025-07-15`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Intel Corporation - SC-1 3065 Bowers` — 1 — 2025-07-15 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is 8 day(s) after the notice date
  - stored name 'Intel Corporation - SC-1 3065 Bowers' differs from the published 'Intel Corporation (Robert Noyce Building)'

### row `138146` — event `2662` — tier `exact`

- stored name: `Intel Corporation (SC-12)`
- stored count **179**, date `2025-07-15`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Intel Corporation (SC-12)` — 179 — 2025-07-15 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is 8 day(s) after the notice date
  - stored name 'Intel Corporation (SC-12)' differs from the published 'Intel Corporation (Robert Noyce Building)'

### row `138145` — event `2661` — tier `exact`

- stored name: `Intel Corporation (SC-11)`
- stored count **8**, date `2025-07-15`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Intel Corporation (SC-11)` — 8 — 2025-07-15 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is 8 day(s) after the notice date
  - stored name 'Intel Corporation (SC-11)' differs from the published 'Intel Corporation (Robert Noyce Building)'

### row `138144` — event `2660` — tier `exact`

- stored name: `Intel Corporation (SC-9)`
- stored count **37**, date `2025-07-15`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Intel Corporation (SC-9)` — 37 — 2025-07-15 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is 8 day(s) after the notice date
  - stored name 'Intel Corporation (SC-9)' differs from the published 'Intel Corporation (Robert Noyce Building)'

### row `138143` — event `2659` — tier `exact`

- stored name: `Intel Corporation (SC-2)`
- stored count **1**, date `2025-07-15`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Intel Corporation (SC-2)` — 1 — 2025-07-15 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is 8 day(s) after the notice date
  - stored name 'Intel Corporation (SC-2)' differs from the published 'Intel Corporation (Robert Noyce Building)'

### row `138142` — event `2658` — tier `exact`

- stored name: `Intel Corporation (SC-1)`
- stored count **1**, date `2025-07-15`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Intel Corporation (SC-1)` — 1 — 2025-07-15 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is 8 day(s) after the notice date
  - stored name 'Intel Corporation (SC-1)' differs from the published 'Intel Corporation (Robert Noyce Building)'

### row `136878` — event `1968` — tier `exact`

- stored name: `Intel Corporation (SC-9)`
- stored count **1**, date `2025-11-30`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Intel Corporation (SC-9)` — 1 — 2025-11-30 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is 146 day(s) after the notice date
  - stored name 'Intel Corporation (SC-9)' differs from the published 'Intel Corporation (Robert Noyce Building)'

### row `136876` — event `1966` — tier `exact`

- stored name: `Intel Corporation (SC-1)`
- stored count **1**, date `2025-11-30`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Intel Corporation (SC-1)` — 1 — 2025-11-30 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is 146 day(s) after the notice date
  - stored name 'Intel Corporation (SC-1)' differs from the published 'Intel Corporation (Robert Noyce Building)'

### row `138207` — event `2703` — tier `loose`

- stored name: `Intel Corporation`
- stored count **54**, date `2025-07-11`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Intel Corporation` — 54 — 2025-07-11 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 54 matches neither a component row nor the notice total 584
  - row date equals this notice's earliest published effective date
  - stored name 'Intel Corporation' differs from the published 'Intel Corporation (Robert Noyce Building)'

### row `138205` — event `2701` — tier `loose`

- stored name: `Intel Corporation`
- stored count **83**, date `2025-07-11`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Intel Corporation` — 83 — 2025-07-11 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 83 matches neither a component row nor the notice total 584
  - row date equals this notice's earliest published effective date
  - stored name 'Intel Corporation' differs from the published 'Intel Corporation (Robert Noyce Building)'

### row `138204` — event `2700` — tier `loose`

- stored name: `Intel Corporation`
- stored count **170**, date `2025-07-11`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Intel Corporation` — 170 — 2025-07-11 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 170 matches neither a component row nor the notice total 584
  - row date equals this notice's earliest published effective date
  - stored name 'Intel Corporation' differs from the published 'Intel Corporation (Robert Noyce Building)'

### row `138165` — event `2681` — tier `loose`

- stored name: `Intel Corporation`
- stored count **45**, date `2025-07-15`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Intel Corporation` — 45 — 2025-07-15 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 45 matches neither a component row nor the notice total 584
  - row date is 8 day(s) after the notice date
  - stored name 'Intel Corporation' differs from the published 'Intel Corporation (Robert Noyce Building)'

### row `138164` — event `2680` — tier `loose`

- stored name: `Intel Corporation - SC-11`
- stored count **2**, date `2025-07-15`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Intel Corporation - SC-11` — 2 — 2025-07-15 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 2 matches neither a component row nor the notice total 584
  - row date is 8 day(s) after the notice date
  - stored name 'Intel Corporation - SC-11' differs from the published 'Intel Corporation (Robert Noyce Building)'

### row `138163` — event `2679` — tier `loose`

- stored name: `Intel Corporation - SC-9`
- stored count **4**, date `2025-07-15`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Intel Corporation - SC-9` — 4 — 2025-07-15 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 4 matches neither a component row nor the notice total 584
  - row date is 8 day(s) after the notice date
  - stored name 'Intel Corporation - SC-9' differs from the published 'Intel Corporation (Robert Noyce Building)'

### row `138160` — event `2676` — tier `loose`

- stored name: `Intel Corporation - Robert Noyce`
- stored count **57**, date `2025-07-15`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Intel Corporation - Robert Noyce` — 57 — 2025-07-15 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 57 matches neither a component row nor the notice total 584
  - row date is 8 day(s) after the notice date
  - stored name 'Intel Corporation - Robert Noyce' differs from the published 'Intel Corporation (Robert Noyce Building)'

### row `138159` — event `2675` — tier `loose`

- stored name: `Intel Corporation - SC-12`
- stored count **26**, date `2025-07-15`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Intel Corporation - SC-12` — 26 — 2025-07-15 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 26 matches neither a component row nor the notice total 584
  - row date is 8 day(s) after the notice date
  - stored name 'Intel Corporation - SC-12' differs from the published 'Intel Corporation (Robert Noyce Building)'

### row `138158` — event `2674` — tier `loose`

- stored name: `Intel Corporation - SC-11`
- stored count **3**, date `2025-07-15`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Intel Corporation - SC-11` — 3 — 2025-07-15 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 3 matches neither a component row nor the notice total 584
  - row date is 8 day(s) after the notice date
  - stored name 'Intel Corporation - SC-11' differs from the published 'Intel Corporation (Robert Noyce Building)'

### row `138157` — event `2673` — tier `loose`

- stored name: `Intel Corporation - SC-9`
- stored count **2**, date `2025-07-15`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Intel Corporation - SC-9` — 2 — 2025-07-15 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 2 matches neither a component row nor the notice total 584
  - row date is 8 day(s) after the notice date
  - stored name 'Intel Corporation - SC-9' differs from the published 'Intel Corporation (Robert Noyce Building)'

### row `138156` — event `2672` — tier `loose`

- stored name: `Intel Corporation - Robert Noyce Building`
- stored count **76**, date `2025-07-15`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Intel Corporation - Robert Noyce Building` — 76 — 2025-07-15 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 76 matches neither a component row nor the notice total 584
  - row date is 8 day(s) after the notice date
  - stored name 'Intel Corporation - Robert Noyce Building' differs from the published 'Intel Corporation (Robert Noyce Building)'

### row `138155` — event `2671` — tier `loose`

- stored name: `Intel Corporation (SC-12)`
- stored count **50**, date `2025-07-15`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Intel Corporation (SC-12)` — 50 — 2025-07-15 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 50 matches neither a component row nor the notice total 584
  - row date is 8 day(s) after the notice date
  - stored name 'Intel Corporation (SC-12)' differs from the published 'Intel Corporation (Robert Noyce Building)'

### row `138154` — event `2670` — tier `loose`

- stored name: `Intel Corporation (SC-9)`
- stored count **2**, date `2025-07-15`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Intel Corporation (SC-9)` — 2 — 2025-07-15 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 2 matches neither a component row nor the notice total 584
  - row date is 8 day(s) after the notice date
  - stored name 'Intel Corporation (SC-9)' differs from the published 'Intel Corporation (Robert Noyce Building)'

### row `138153` — event `2669` — tier `loose`

- stored name: `Intel Corporation (Robert Noyce)`
- stored count **46**, date `2025-07-15`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Intel Corporation (Robert Noyce)` — 46 — 2025-07-15 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 46 matches neither a component row nor the notice total 584
  - row date is 8 day(s) after the notice date
  - stored name 'Intel Corporation (Robert Noyce)' differs from the published 'Intel Corporation (Robert Noyce Building)'

### row `138152` — event `2668` — tier `loose`

- stored name: `Intel Corporation (SC-12)`
- stored count **55**, date `2025-07-15`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Intel Corporation (SC-12)` — 55 — 2025-07-15 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 55 matches neither a component row nor the notice total 584
  - row date is 8 day(s) after the notice date
  - stored name 'Intel Corporation (SC-12)' differs from the published 'Intel Corporation (Robert Noyce Building)'

### row `138151` — event `2667` — tier `loose`

- stored name: `Intel Corporation (SC-11)`
- stored count **5**, date `2025-07-15`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Intel Corporation (SC-11)` — 5 — 2025-07-15 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 5 matches neither a component row nor the notice total 584
  - row date is 8 day(s) after the notice date
  - stored name 'Intel Corporation (SC-11)' differs from the published 'Intel Corporation (Robert Noyce Building)'

### row `138150` — event `2666` — tier `loose`

- stored name: `Intel Corporation (SC-9)`
- stored count **16**, date `2025-07-15`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Intel Corporation (SC-9)` — 16 — 2025-07-15 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 16 matches neither a component row nor the notice total 584
  - row date is 8 day(s) after the notice date
  - stored name 'Intel Corporation (SC-9)' differs from the published 'Intel Corporation (Robert Noyce Building)'

### row `138149` — event `2665` — tier `loose`

- stored name: `Intel Corporation (SC-2)`
- stored count **43**, date `2025-07-15`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Intel Corporation (SC-2)` — 43 — 2025-07-15 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 43 matches neither a component row nor the notice total 584
  - row date is 8 day(s) after the notice date
  - stored name 'Intel Corporation (SC-2)' differs from the published 'Intel Corporation (Robert Noyce Building)'

### row `138148` — event `2664` — tier `loose`

- stored name: `Intel Corporation (SC-1)`
- stored count **4**, date `2025-07-15`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Intel Corporation (SC-1)` — 4 — 2025-07-15 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 4 matches neither a component row nor the notice total 584
  - row date is 8 day(s) after the notice date
  - stored name 'Intel Corporation (SC-1)' differs from the published 'Intel Corporation (Robert Noyce Building)'

### row `138147` — event `2663` — tier `loose`

- stored name: `Intel Corporation (Robert Noyce)`
- stored count **203**, date `2025-07-15`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Intel Corporation (Robert Noyce)` — 203 — 2025-07-15 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 203 matches neither a component row nor the notice total 584
  - row date is 8 day(s) after the notice date
  - stored name 'Intel Corporation (Robert Noyce)' differs from the published 'Intel Corporation (Robert Noyce Building)'

### row `136879` — event `1969` — tier `loose`

- stored name: `Intel Corporation (SC-12)`
- stored count **10**, date `2025-11-30`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Intel Corporation (SC-12)` — 10 — 2025-11-30 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 10 matches neither a component row nor the notice total 584
  - row date is 146 day(s) after the notice date
  - stored name 'Intel Corporation (SC-12)' differs from the published 'Intel Corporation (Robert Noyce Building)'

### row `136877` — event `1967` — tier `loose`

- stored name: `Intel Corporation (SC-2)`
- stored count **2**, date `2025-11-30`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Intel Corporation (SC-2)` — 2 — 2025-11-30 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 2 matches neither a component row nor the notice total 584
  - row date is 146 day(s) after the notice date
  - stored name 'Intel Corporation (SC-2)' differs from the published 'Intel Corporation (Robert Noyce Building)'

---

## 4. Quanex Homeshield LLC (CA)

`warn-ca-2025-07-11-quanex-homeshield` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-07-11**, effective 2025-09-09..2025-09-09
- **15** affected across 1 published row(s)
  - Quanex Homeshield LLC — 15 — San Bernardino County; 13611 Santa Ana Avenue  Fontana CA 92337 — `page 22, text row at y=86.6`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2025-06-11 .. 2026-08-15

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `137666` — event `2414` — tier `exact`

- stored name: `Quanex Homeshield LLC`
- stored count **15**, date `2025-09-09`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Quanex Homeshield LLC` — 15 — 2025-09-09 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 5. Decra Roofing Systems, Inc. (CA)

`warn-ca-2025-07-28-decra-roofing-systems` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-07-28**, effective 2025-09-30..2025-09-30
- **61** affected across 2 published row(s)
  - Decra Roofing Systems, Inc. — 57 — Riverside County; 1230 Railroad Street  Corona CA 92882 — `page 1, text row at y=139.6`
  - Decra Roofing Systems, Inc. — 4 — Riverside County; 1230 Railroad St.  Corona CA 92882 — `page 1, text row at y=64.0`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2025-06-28 .. 2026-09-01

**2 candidate row(s).** Each block below is one row and says nothing about any other.

### row `137465` — event `2306` — tier `exact`

- stored name: `Decra Roofing Systems, Inc.`
- stored count **4**, date `2025-09-30`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Decra Roofing Systems, Inc.` — 4 — 2025-09-30 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `137464` — event `2305` — tier `exact`

- stored name: `Decra Roofing Systems, Inc.`
- stored count **57**, date `2025-09-30`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Decra Roofing Systems, Inc.` — 57 — 2025-09-30 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 6. Bausch Health US, LLC (CA)

`warn-ca-2025-08-13-bausch-health` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-08-13**, effective 2025-08-13..2025-08-13
- **49** affected across 1 published row(s)
  - Bausch Health US, LLC — 49 — Sonoma County; 1330 Redwood Way  Petaluma CA 94954 — `page 2, text row at y=207.6`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2025-07-14 .. 2026-09-17

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `137919` — event `2530` — tier `exact`

- stored name: `Bausch Health US, LLC`
- stored count **49**, date `2025-08-13`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Bausch Health US, LLC` — 49 — 2025-08-13 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 7. Enloe Health (CA)

`warn-ca-2025-08-25-enloe-health` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-08-25**, effective 2025-10-31..2025-10-31
- **78** affected across 1 published row(s)
  - Enloe Health — 78 — Butte County; 1390 E. Lassen Avenue  Chico CA 95973 — `page 3, text row at y=472.2`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2025-07-26 .. 2026-09-29

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `137166` — event `2120` — tier `exact`

- stored name: `Enloe Health`
- stored count **78**, date `2025-10-31`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Enloe Health` — 78 — 2025-10-31 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 8. Essendant (CA)

`warn-ca-2025-09-04-essendant` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-09-04**, effective 2025-12-31..2025-12-31
- **146** affected across 1 published row(s)
  - Essendant — 146 — Riverside County; 4555 Redlands Ave  Perris CA 92571 — `page 3, text row at y=64.0`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2025-08-05 .. 2026-10-09

**3 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136567` — event `1794` — tier `exact`

- stored name: `Essendant`
- stored count **146**, date `2025-12-31`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Essendant` — 146 — 2025-12-31 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `177210` — event `149943` — tier `loose`

- stored name: `Essendant Co.`
- stored count **99**, date `2026-10-03`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Essendant Co.` — 99 — 2026-10-03 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 99 matches neither a component row nor the notice total 146
  - row date is 394 day(s) after the notice date
  - stored name 'Essendant Co.' differs from the published 'Essendant'

### row `177209` — event `149942` — tier `loose`

- stored name: `Essendant Co.`
- stored count **4**, date `2026-10-03`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Essendant Co.` — 4 — 2026-10-03 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 4 matches neither a component row nor the notice total 146
  - row date is 394 day(s) after the notice date
  - stored name 'Essendant Co.' differs from the published 'Essendant'

---

## 9. Dreyer's Grand Ice Cream (CA)

`warn-ca-2025-09-23-dreyer-s-grand-ice` — currently `not_matched`, stratum `large_census`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-09-23**, effective 2025-11-23..2025-11-24
- **914** affected across 2 published row(s)
  - Dreyer's Grand Ice Cream — 188 — Tulare County; 970 E. Continental  Tulare CA 93274 — `page 4, text row at y=283.2`
  - Dreyer's Grand Ice Cream — 726 — Kern County; 7301 District Boulevard  Bakersfield CA 93313 — `page 4, text row at y=124.4`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2025-08-24 .. 2026-10-28

**2 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136937` — event `1998` — tier `exact`

- stored name: `Dreyer's Grand Ice Cream`
- stored count **726**, date `2025-11-23`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Dreyer's Grand Ice Cream` — 726 — 2025-11-23 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `136926` — event `1989` — tier `exact`

- stored name: `Dreyer's Grand Ice Cream`
- stored count **188**, date `2025-11-24`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Dreyer's Grand Ice Cream` — 188 — 2025-11-24 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is 62 day(s) after the notice date

---

## 10. Palo Verde Healthcare District (CA)

`warn-ca-2025-09-24-palo-verde-healthcare-district` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-09-24**, effective 2025-11-23..2025-11-23
- **94** affected across 1 published row(s)
  - Palo Verde Healthcare District — 94 — Riverside County; 250 N First Street  Blythe CA 92225 — `page 4, text row at y=268.1`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2025-08-25 .. 2026-10-29

**2 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136935` — event `1996` — tier `exact`

- stored name: `Palo Verde Healthcare District`
- stored count **94**, date `2025-11-23`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Palo Verde Healthcare District` — 94 — 2025-11-23 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `136350` — event `1641` — tier `loose`

- stored name: `Palo Verde Hospital`
- stored count **99**, date `2026-01-24`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Palo Verde Hospital` — 99 — 2026-01-24 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 99 matches neither a component row nor the notice total 94
  - row date is 122 day(s) after the notice date
  - stored name 'Palo Verde Hospital' differs from the published 'Palo Verde Healthcare District'

---

## 11. Amazon (CA)

`warn-ca-2025-10-02-amazon` — currently `not_matched`, stratum `large_census`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-10-02**, effective 2026-01-06..2026-01-06
- **555** affected across 4 published row(s)
  - Amazon — 149 — Orange County; 26940 Crown Valley Pkwy.  Mission Viejo CA 92691 — `page 5, text row at y=502.4`
  - Amazon — 107 — Los Angeles County; 2229 Foothill Blvd  La Verne CA 91750 — `page 5, text row at y=426.8`
  - Amazon — 126 — Los Angeles County; 15225 Whittier Blvd.  Whittier CA 90603 — `page 5, text row at y=419.3`
  - Amazon — 173 — Orange County; 1610 W Imperial Hwy  La Habra CA 90631 — `page 5, text row at y=404.2`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2025-09-02 .. 2026-11-06

**92 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136455` — event `1705` — tier `exact`

- stored name: `Amazon`
- stored count **173**, date `2026-01-06`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon` — 173 — 2026-01-06 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `136454` — event `1704` — tier `exact`

- stored name: `Amazon`
- stored count **126**, date `2026-01-06`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon` — 126 — 2026-01-06 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `136453` — event `1703` — tier `exact`

- stored name: `Amazon`
- stored count **107**, date `2026-01-06`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon` — 107 — 2026-01-06 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `136452` — event `1702` — tier `exact`

- stored name: `Amazon`
- stored count **149**, date `2026-01-06`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon` — 149 — 2026-01-06 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `135379` — event `1155` — tier `loose`

- stored name: `Amazon`
- stored count **89**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon` — 89 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 89 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date

### row `135378` — event `1154` — tier `loose`

- stored name: `Amazon`
- stored count **81**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon` — 81 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 81 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date

### row `135377` — event `1153` — tier `loose`

- stored name: `Amazon`
- stored count **87**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon` — 87 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 87 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date

### row `135376` — event `1152` — tier `loose`

- stored name: `Amazon`
- stored count **58**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon` — 58 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 58 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date

### row `135375` — event `1151` — tier `loose`

- stored name: `Amazon`
- stored count **11**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon` — 11 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 11 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date

### row `135374` — event `1150` — tier `loose`

- stored name: `Amazon`
- stored count **3**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon` — 3 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 3 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date

### row `135373` — event `1149` — tier `loose`

- stored name: `Amazon`
- stored count **32**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon` — 32 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 32 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date

### row `135372` — event `1148` — tier `loose`

- stored name: `Amazon`
- stored count **72**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon` — 72 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 72 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date

### row `136333` — event `1632` — tier `loose`

- stored name: `Amazon (SFO38)`
- stored count **3**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SFO38)` — 3 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 3 matches neither a component row nor the notice total 555
  - row date is 116 day(s) after the notice date
  - stored name 'Amazon (SFO38)' differs from the published 'Amazon'

### row `136332` — event `1631` — tier `loose`

- stored name: `Amazon (SFO28)`
- stored count **71**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SFO28)` — 71 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 71 matches neither a component row nor the notice total 555
  - row date is 116 day(s) after the notice date
  - stored name 'Amazon (SFO28)' differs from the published 'Amazon'

### row `136331` — event `1630` — tier `loose`

- stored name: `Amazon (SFO19)`
- stored count **18**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SFO19)` — 18 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 18 matches neither a component row nor the notice total 555
  - row date is 116 day(s) after the notice date
  - stored name 'Amazon (SFO19)' differs from the published 'Amazon'

### row `136330` — event `1629` — tier `loose`

- stored name: `Amazon (SFO13)`
- stored count **41**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SFO13)` — 41 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 41 matches neither a component row nor the notice total 555
  - row date is 116 day(s) after the notice date
  - stored name 'Amazon (SFO13)' differs from the published 'Amazon'

### row `136329` — event `1628` — tier `loose`

- stored name: `Amazon (ONM213)`
- stored count **1**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (ONM213)` — 1 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 1 matches neither a component row nor the notice total 555
  - row date is 116 day(s) after the notice date
  - stored name 'Amazon (ONM213)' differs from the published 'Amazon'

### row `136328` — event `1627` — tier `loose`

- stored name: `Amazon (ONM212)`
- stored count **3**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (ONM212)` — 3 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 3 matches neither a component row nor the notice total 555
  - row date is 116 day(s) after the notice date
  - stored name 'Amazon (ONM212)' differs from the published 'Amazon'

### row `136327` — event `1626` — tier `loose`

- stored name: `Amazon (SAN 5)`
- stored count **1**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SAN 5)` — 1 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 1 matches neither a component row nor the notice total 555
  - row date is 116 day(s) after the notice date
  - stored name 'Amazon (SAN 5)' differs from the published 'Amazon'

### row `136326` — event `1625` — tier `loose`

- stored name: `Amazon (SAN 3)`
- stored count **1**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SAN 3)` — 1 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 1 matches neither a component row nor the notice total 555
  - row date is 116 day(s) after the notice date
  - stored name 'Amazon (SAN 3)' differs from the published 'Amazon'

### row `136325` — event `1624` — tier `loose`

- stored name: `Amazon (SAN 21)`
- stored count **5**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SAN 21)` — 5 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 5 matches neither a component row nor the notice total 555
  - row date is 116 day(s) after the notice date
  - stored name 'Amazon (SAN 21)' differs from the published 'Amazon'

### row `136324` — event `1623` — tier `loose`

- stored name: `Amazon (SAN 18)`
- stored count **3**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SAN 18)` — 3 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 3 matches neither a component row nor the notice total 555
  - row date is 116 day(s) after the notice date
  - stored name 'Amazon (SAN 18)' differs from the published 'Amazon'

### row `136323` — event `1622` — tier `loose`

- stored name: `Amazon (SAN 17)`
- stored count **61**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SAN 17)` — 61 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 61 matches neither a component row nor the notice total 555
  - row date is 116 day(s) after the notice date
  - stored name 'Amazon (SAN 17)' differs from the published 'Amazon'

### row `136322` — event `1621` — tier `loose`

- stored name: `Amazon (SAN 15)`
- stored count **50**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SAN 15)` — 50 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 50 matches neither a component row nor the notice total 555
  - row date is 116 day(s) after the notice date
  - stored name 'Amazon (SAN 15)' differs from the published 'Amazon'

### row `136321` — event `1620` — tier `loose`

- stored name: `Amazon (SAN 13)`
- stored count **24**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SAN 13)` — 24 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 24 matches neither a component row nor the notice total 555
  - row date is 116 day(s) after the notice date
  - stored name 'Amazon (SAN 13)' differs from the published 'Amazon'

### row `136320` — event `1619` — tier `loose`

- stored name: `Amazon SNA3`
- stored count **45**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SNA3` — 45 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 45 matches neither a component row nor the notice total 555
  - row date is 116 day(s) after the notice date
  - stored name 'Amazon SNA3' differs from the published 'Amazon'

### row `136319` — event `1618` — tier `loose`

- stored name: `Amazon SNA19`
- stored count **16**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SNA19` — 16 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 16 matches neither a component row nor the notice total 555
  - row date is 116 day(s) after the notice date
  - stored name 'Amazon SNA19' differs from the published 'Amazon'

### row `136318` — event `1617` — tier `loose`

- stored name: `Amazon SNA18`
- stored count **1**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SNA18` — 1 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 1 matches neither a component row nor the notice total 555
  - row date is 116 day(s) after the notice date
  - stored name 'Amazon SNA18' differs from the published 'Amazon'

### row `136317` — event `1616` — tier `loose`

- stored name: `Amazon SNA17`
- stored count **12**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SNA17` — 12 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 12 matches neither a component row nor the notice total 555
  - row date is 116 day(s) after the notice date
  - stored name 'Amazon SNA17' differs from the published 'Amazon'

### row `136316` — event `1615` — tier `loose`

- stored name: `Amazon SNA16`
- stored count **64**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SNA16` — 64 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 64 matches neither a component row nor the notice total 555
  - row date is 116 day(s) after the notice date
  - stored name 'Amazon SNA16' differs from the published 'Amazon'

### row `136315` — event `1614` — tier `loose`

- stored name: `Amazon SNA12`
- stored count **17**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SNA12` — 17 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 17 matches neither a component row nor the notice total 555
  - row date is 116 day(s) after the notice date
  - stored name 'Amazon SNA12' differs from the published 'Amazon'

### row `136314` — event `1613` — tier `loose`

- stored name: `Amazon SNA11`
- stored count **178**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SNA11` — 178 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 178 matches neither a component row nor the notice total 555
  - row date is 116 day(s) after the notice date
  - stored name 'Amazon SNA11' differs from the published 'Amazon'

### row `136313` — event `1612` — tier `loose`

- stored name: `Amazon SJC44`
- stored count **18**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SJC44` — 18 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 18 matches neither a component row nor the notice total 555
  - row date is 116 day(s) after the notice date
  - stored name 'Amazon SJC44' differs from the published 'Amazon'

### row `136312` — event `1611` — tier `loose`

- stored name: `Amazon SJC38`
- stored count **50**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SJC38` — 50 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 50 matches neither a component row nor the notice total 555
  - row date is 116 day(s) after the notice date
  - stored name 'Amazon SJC38' differs from the published 'Amazon'

### row `136311` — event `1610` — tier `loose`

- stored name: `Amazon SJC25`
- stored count **8**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SJC25` — 8 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 8 matches neither a component row nor the notice total 555
  - row date is 116 day(s) after the notice date
  - stored name 'Amazon SJC25' differs from the published 'Amazon'

### row `136310` — event `1609` — tier `loose`

- stored name: `Amazon SFO39`
- stored count **2**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SFO39` — 2 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 2 matches neither a component row nor the notice total 555
  - row date is 116 day(s) after the notice date
  - stored name 'Amazon SFO39' differs from the published 'Amazon'

### row `136309` — event `1608` — tier `loose`

- stored name: `Amazon SFO36`
- stored count **12**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SFO36` — 12 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 12 matches neither a component row nor the notice total 555
  - row date is 116 day(s) after the notice date
  - stored name 'Amazon SFO36' differs from the published 'Amazon'

### row `136308` — event `1607` — tier `loose`

- stored name: `Amazon SFO24`
- stored count **75**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SFO24` — 75 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 75 matches neither a component row nor the notice total 555
  - row date is 116 day(s) after the notice date
  - stored name 'Amazon SFO24' differs from the published 'Amazon'

### row `136307` — event `1606` — tier `loose`

- stored name: `Amazon SFO22`
- stored count **69**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SFO22` — 69 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 69 matches neither a component row nor the notice total 555
  - row date is 116 day(s) after the notice date
  - stored name 'Amazon SFO22' differs from the published 'Amazon'

### row `136306` — event `1605` — tier `loose`

- stored name: `Amazon SFO12`
- stored count **18**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SFO12` — 18 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 18 matches neither a component row nor the notice total 555
  - row date is 116 day(s) after the notice date
  - stored name 'Amazon SFO12' differs from the published 'Amazon'

### row `136305` — event `1604` — tier `loose`

- stored name: `Amazon (SJC32)`
- stored count **85**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SJC32)` — 85 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 85 matches neither a component row nor the notice total 555
  - row date is 116 day(s) after the notice date
  - stored name 'Amazon (SJC32)' differs from the published 'Amazon'

### row `136304` — event `1603` — tier `loose`

- stored name: `Amazon (SJC31)`
- stored count **27**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SJC31)` — 27 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 27 matches neither a component row nor the notice total 555
  - row date is 116 day(s) after the notice date
  - stored name 'Amazon (SJC31)' differs from the published 'Amazon'

### row `136303` — event `1602` — tier `loose`

- stored name: `Amazon (SJC14)`
- stored count **80**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SJC14)` — 80 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 80 matches neither a component row nor the notice total 555
  - row date is 116 day(s) after the notice date
  - stored name 'Amazon (SJC14)' differs from the published 'Amazon'

### row `136302` — event `1601` — tier `loose`

- stored name: `Amazon (SJC13)`
- stored count **33**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SJC13)` — 33 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 33 matches neither a component row nor the notice total 555
  - row date is 116 day(s) after the notice date
  - stored name 'Amazon (SJC13)' differs from the published 'Amazon'

### row `136301` — event `1600` — tier `loose`

- stored name: `Amazon (SJC11)`
- stored count **28**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SJC11)` — 28 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 28 matches neither a component row nor the notice total 555
  - row date is 116 day(s) after the notice date
  - stored name 'Amazon (SJC11)' differs from the published 'Amazon'

### row `136300` — event `1599` — tier `loose`

- stored name: `Amazon (SJC10)`
- stored count **138**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SJC10)` — 138 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 138 matches neither a component row nor the notice total 555
  - row date is 116 day(s) after the notice date
  - stored name 'Amazon (SJC10)' differs from the published 'Amazon'

### row `136299` — event `1598` — tier `loose`

- stored name: `Amazon LAX78`
- stored count **65**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon LAX78` — 65 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 65 matches neither a component row nor the notice total 555
  - row date is 116 day(s) after the notice date
  - stored name 'Amazon LAX78' differs from the published 'Amazon'

### row `136298` — event `1597` — tier `loose`

- stored name: `Amazon LAX16`
- stored count **3**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon LAX16` — 3 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 3 matches neither a component row nor the notice total 555
  - row date is 116 day(s) after the notice date
  - stored name 'Amazon LAX16' differs from the published 'Amazon'

### row `136297` — event `1596` — tier `loose`

- stored name: `Amazon LAX10`
- stored count **62**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon LAX10` — 62 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 62 matches neither a component row nor the notice total 555
  - row date is 116 day(s) after the notice date
  - stored name 'Amazon LAX10' differs from the published 'Amazon'

### row `136296` — event `1595` — tier `loose`

- stored name: `Amazon LAX21`
- stored count **43**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon LAX21` — 43 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 43 matches neither a component row nor the notice total 555
  - row date is 116 day(s) after the notice date
  - stored name 'Amazon LAX21' differs from the published 'Amazon'

### row `136295` — event `1594` — tier `loose`

- stored name: `Amazon LAX22`
- stored count **65**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon LAX22` — 65 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 65 matches neither a component row nor the notice total 555
  - row date is 116 day(s) after the notice date
  - stored name 'Amazon LAX22' differs from the published 'Amazon'

### row `135392` — event `1168` — tier `loose`

- stored name: `Amazon - SFO 28`
- stored count **84**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - SFO 28` — 84 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 84 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon - SFO 28' differs from the published 'Amazon'

### row `135391` — event `1167` — tier `loose`

- stored name: `Amazon - SFO 13`
- stored count **19**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - SFO 13` — 19 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 19 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon - SFO 13' differs from the published 'Amazon'

### row `135390` — event `1166` — tier `loose`

- stored name: `Amazon - SAN 3`
- stored count **1**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - SAN 3` — 1 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 1 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon - SAN 3' differs from the published 'Amazon'

### row `135389` — event `1165` — tier `loose`

- stored name: `Amazon - SAN 21`
- stored count **2**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - SAN 21` — 2 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 2 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon - SAN 21' differs from the published 'Amazon'

### row `135388` — event `1164` — tier `loose`

- stored name: `Amazon - SAN 18`
- stored count **13**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - SAN 18` — 13 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 13 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon - SAN 18' differs from the published 'Amazon'

### row `135387` — event `1163` — tier `loose`

- stored name: `Amazon - SAN 17`
- stored count **19**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - SAN 17` — 19 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 19 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon - SAN 17' differs from the published 'Amazon'

### row `135386` — event `1162` — tier `loose`

- stored name: `Amazon - SAN 15`
- stored count **1**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - SAN 15` — 1 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 1 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon - SAN 15' differs from the published 'Amazon'

### row `135385` — event `1161` — tier `loose`

- stored name: `Amazon - SAN 13`
- stored count **38**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - SAN 13` — 38 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 38 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon - SAN 13' differs from the published 'Amazon'

### row `135384` — event `1160` — tier `loose`

- stored name: `Amazon - SNA 3`
- stored count **34**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - SNA 3` — 34 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 34 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon - SNA 3' differs from the published 'Amazon'

### row `135383` — event `1159` — tier `loose`

- stored name: `Amazon - SNA 20`
- stored count **25**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - SNA 20` — 25 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 25 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon - SNA 20' differs from the published 'Amazon'

### row `135382` — event `1158` — tier `loose`

- stored name: `Amazon - SNA 17`
- stored count **1**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - SNA 17` — 1 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 1 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon - SNA 17' differs from the published 'Amazon'

### row `135381` — event `1157` — tier `loose`

- stored name: `Amazon - SNA 16`
- stored count **24**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - SNA 16` — 24 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 24 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon - SNA 16' differs from the published 'Amazon'

### row `135380` — event `1156` — tier `loose`

- stored name: `Amazon - SNA12`
- stored count **5**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - SNA12` — 5 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 5 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon - SNA12' differs from the published 'Amazon'

### row `135371` — event `1147` — tier `loose`

- stored name: `Amazon (SJC44)`
- stored count **49**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SJC44)` — 49 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 49 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon (SJC44)' differs from the published 'Amazon'

### row `135370` — event `1146` — tier `loose`

- stored name: `Amazon (SJC38)`
- stored count **141**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SJC38)` — 141 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 141 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon (SJC38)' differs from the published 'Amazon'

### row `135369` — event `1145` — tier `loose`

- stored name: `Amazon (SJC25)`
- stored count **43**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SJC25)` — 43 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 43 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon (SJC25)' differs from the published 'Amazon'

### row `135368` — event `1144` — tier `loose`

- stored name: `Amazon (LAX78)`
- stored count **45**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (LAX78)` — 45 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 45 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon (LAX78)' differs from the published 'Amazon'

### row `135367` — event `1143` — tier `loose`

- stored name: `Amazon (LAX16)`
- stored count **46**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (LAX16)` — 46 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 46 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon (LAX16)' differs from the published 'Amazon'

### row `135366` — event `1142` — tier `loose`

- stored name: `Amazon (LAX10)`
- stored count **2**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (LAX10)` — 2 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 2 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon (LAX10)' differs from the published 'Amazon'

### row `135365` — event `1141` — tier `loose`

- stored name: `Amazon - MAM7`
- stored count **139**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAM7` — 139 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 139 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon - MAM7' differs from the published 'Amazon'

### row `135364` — event `1140` — tier `loose`

- stored name: `Amazon - MAO6`
- stored count **189**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAO6` — 189 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 189 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon - MAO6' differs from the published 'Amazon'

### row `135363` — event `1139` — tier `loose`

- stored name: `Amazon - MAF5`
- stored count **190**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAF5` — 190 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 190 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon - MAF5' differs from the published 'Amazon'

### row `135362` — event `1138` — tier `loose`

- stored name: `Amazon - MAQ8`
- stored count **163**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAQ8` — 163 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 163 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon - MAQ8' differs from the published 'Amazon'

### row `135361` — event `1137` — tier `loose`

- stored name: `Amazon - MAM9`
- stored count **179**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAM9` — 179 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 179 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon - MAM9' differs from the published 'Amazon'

### row `135360` — event `1136` — tier `loose`

- stored name: `Amazon - MAJ8`
- stored count **160**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAJ8` — 160 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 160 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon - MAJ8' differs from the published 'Amazon'

### row `135359` — event `1135` — tier `loose`

- stored name: `Amazon - MAI8`
- stored count **182**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAI8` — 182 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 182 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon - MAI8' differs from the published 'Amazon'

### row `135358` — event `1134` — tier `loose`

- stored name: `Amazon - MAH8`
- stored count **172**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAH8` — 172 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 172 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon - MAH8' differs from the published 'Amazon'

### row `135357` — event `1133` — tier `loose`

- stored name: `Amazon - MAQ9`
- stored count **174**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAQ9` — 174 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 174 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon - MAQ9' differs from the published 'Amazon'

### row `135356` — event `1132` — tier `loose`

- stored name: `Amazon - MBA6`
- stored count **181**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MBA6` — 181 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 181 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon - MBA6' differs from the published 'Amazon'

### row `135355` — event `1131` — tier `loose`

- stored name: `Amazon - MAC2`
- stored count **175**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAC2` — 175 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 175 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon - MAC2' differs from the published 'Amazon'

### row `135354` — event `1130` — tier `loose`

- stored name: `Amazon - MAB9`
- stored count **191**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAB9` — 191 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 191 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon - MAB9' differs from the published 'Amazon'

### row `135353` — event `1129` — tier `loose`

- stored name: `Amazon - MAB8`
- stored count **191**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAB8` — 191 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 191 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon - MAB8' differs from the published 'Amazon'

### row `135352` — event `1128` — tier `loose`

- stored name: `Amazon - MAK9`
- stored count **134**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAK9` — 134 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 134 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon - MAK9' differs from the published 'Amazon'

### row `135351` — event `1127` — tier `loose`

- stored name: `Amazon - MAG1`
- stored count **185**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAG1` — 185 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 185 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon - MAG1' differs from the published 'Amazon'

### row `135350` — event `1126` — tier `loose`

- stored name: `Amazon - MAF9`
- stored count **155**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAF9` — 155 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 155 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon - MAF9' differs from the published 'Amazon'

### row `135349` — event `1125` — tier `loose`

- stored name: `Amazon - MAF8`
- stored count **196**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAF8` — 196 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 196 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon - MAF8' differs from the published 'Amazon'

### row `135348` — event `1124` — tier `loose`

- stored name: `Amazon - MAF3`
- stored count **201**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAF3` — 201 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 201 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon - MAF3' differs from the published 'Amazon'

### row `135347` — event `1123` — tier `loose`

- stored name: `Amazon - MAC9`
- stored count **168**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAC9` — 168 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 168 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon - MAC9' differs from the published 'Amazon'

### row `135346` — event `1122` — tier `loose`

- stored name: `Amazon - MAB5`
- stored count **184**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAB5` — 184 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 184 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon - MAB5' differs from the published 'Amazon'

### row `135345` — event `1121` — tier `loose`

- stored name: `Amazon - MAB4`
- stored count **131**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAB4` — 131 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 131 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon - MAB4' differs from the published 'Amazon'

### row `135344` — event `1120` — tier `loose`

- stored name: `Amazon - MAB1`
- stored count **215**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAB1` — 215 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 215 matches neither a component row nor the notice total 555
  - row date is 208 day(s) after the notice date
  - stored name 'Amazon - MAB1' differs from the published 'Amazon'

---

## 12. Manna Beverages MBV-CA LLC - 1226 (CA)

`warn-ca-2025-10-03-manna-beverages-mbv-ca` — currently `not_matched`, stratum `large_census`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-10-03**, effective 2025-10-07..2025-10-07
- **638** affected across 6 published row(s)
  - Manna Beverages MBV-CA LLC - 1226 — 245 — Orange County; 1226 North Olive Street  Anaheim CA 92801 — `page 5, text row at y=479.8`
  - Manna Beverages MBV-CA LLC 6725 — 15 — San Bernardino County; 6728 Kimball Ave  Chino CA 91708 — `page 5, text row at y=472.2`
  - Manna Beverages MBV-CA LLC - 2150 — 25 — Yolo County; 2150 Stone Blvd.  West Sacramento CA 95691 — `page 5, text row at y=464.6`
  - Manna Beverages MBV-CA LLC 2286 — 237 — Yolo County; 2286 Stone Blvd  West Sacramento CA 95691 — `page 5, text row at y=457.1`
  - Manna Beverages MBV-CA LLC 3600 — 98 — Yolo County; 3600 Massie Court  West Sacramento CA 95691 — `page 5, text row at y=449.5`
  - Manna Beverages MBV-CA LLC 3685 — 18 — Yolo County; 3685 Massie Court  West Sacramento CA 95691 — `page 5, text row at y=442.0`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2025-09-03 .. 2026-11-07

**6 candidate row(s).** Each block below is one row and says nothing about any other.

### row `137337` — event `2223` — tier `exact`

- stored name: `Manna Beverages MBV-CA LLC - 1226`
- stored count **245**, date `2025-10-07`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Manna Beverages MBV-CA LLC - 1226` — 245 — 2025-10-07 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `137342` — event `2228` — tier `exact`

- stored name: `Manna Beverages MBV-CA LLC 3685`
- stored count **18**, date `2025-10-07`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Manna Beverages MBV-CA LLC 3685` — 18 — 2025-10-07 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Manna Beverages MBV-CA LLC 3685' differs from the published 'Manna Beverages MBV-CA LLC - 1226'

### row `137341` — event `2227` — tier `exact`

- stored name: `Manna Beverages MBV-CA LLC 3600`
- stored count **98**, date `2025-10-07`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Manna Beverages MBV-CA LLC 3600` — 98 — 2025-10-07 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Manna Beverages MBV-CA LLC 3600' differs from the published 'Manna Beverages MBV-CA LLC - 1226'

### row `137340` — event `2226` — tier `exact`

- stored name: `Manna Beverages MBV-CA LLC 2286`
- stored count **237**, date `2025-10-07`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Manna Beverages MBV-CA LLC 2286` — 237 — 2025-10-07 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Manna Beverages MBV-CA LLC 2286' differs from the published 'Manna Beverages MBV-CA LLC - 1226'

### row `137339` — event `2225` — tier `exact`

- stored name: `Manna Beverages MBV-CA LLC - 2150`
- stored count **25**, date `2025-10-07`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Manna Beverages MBV-CA LLC - 2150` — 25 — 2025-10-07 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Manna Beverages MBV-CA LLC - 2150' differs from the published 'Manna Beverages MBV-CA LLC - 1226'

### row `137338` — event `2224` — tier `exact`

- stored name: `Manna Beverages MBV-CA LLC 6725`
- stored count **15**, date `2025-10-07`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Manna Beverages MBV-CA LLC 6725` — 15 — 2025-10-07 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Manna Beverages MBV-CA LLC 6725' differs from the published 'Manna Beverages MBV-CA LLC - 1226'

---

## 13. SAP America, Inc. (CA)

`warn-ca-2025-10-06-sap-america` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-10-06**, effective 2025-11-21..2025-11-21
- **82** affected across 1 published row(s)
  - SAP America, Inc. — 82 — Santa Clara County; 3410 Hillview Avenue  Palo Alto CA 94304 — `page 5, text row at y=358.8`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2025-09-06 .. 2026-11-10

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136946` — event `2006` — tier `exact`

- stored name: `SAP America, Inc.`
- stored count **82**, date `2025-11-21`, state `CA`, source `warn` / `CA WARN notice`
- live now: `SAP America, Inc.` — 82 — 2025-11-21 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 14. Jet Propulsion Laboratory (California Institute of Technology) (CA)

`warn-ca-2025-10-14-jet-propulsion-laboratory` — currently `not_matched`, stratum `large_census`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-10-14**, effective 2025-12-13..2025-12-13
- **543** affected across 1 published row(s)
  - Jet Propulsion Laboratory (California Institute of Technology) — 543 — Los Angeles County; 4800 Oak Grove Drive  La Canada Flintridge CA 91011 — `page 6, text row at y=525.1`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2025-09-14 .. 2026-11-18

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136767` — event `1915` — tier `exact`

- stored name: `Jet Propulsion Laboratory (California Institute of Technology)`
- stored count **543**, date `2025-12-13`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Jet Propulsion Laboratory (California Institute of Technology)` — 543 — 2025-12-13 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 15. Centene Management Company, LLC (CA)

`warn-ca-2025-10-20-centene-management` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-10-20**, effective 2025-12-19..2025-12-19
- **5** affected across 1 published row(s)
  - Centene Management Company, LLC — 5 — Sacramento County; 12033 Foundation Place  Rancho Cordova CA 95670 — `page 6, text row at y=351.2`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2025-09-20 .. 2026-11-24

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136710` — event `1881` — tier `exact`

- stored name: `Centene Management Company, LLC`
- stored count **5**, date `2025-12-19`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Centene Management Company, LLC` — 5 — 2025-12-19 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 16. Ojai Valley Inn (CA)

`warn-ca-2025-10-20-ojai-valley-inn` — currently `not_matched`, stratum `large_census`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-10-20**, effective 2026-01-04..2026-01-04
- **773** affected across 1 published row(s)
  - Ojai Valley Inn — 773 — Ventura County; 905 Country Club Road  Ojai CA 93023 — `page 6, text row at y=313.4`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2025-09-20 .. 2026-11-24

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136478` — event `1714` — tier `exact`

- stored name: `Ojai Valley Inn`
- stored count **773**, date `2026-01-04`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Ojai Valley Inn` — 773 — 2026-01-04 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 17. Amazon SFO12 (CA)

`warn-ca-2025-10-28-amazon-sfo12` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-10-28**, effective 2026-01-26..2026-01-26
- **18** affected across 1 published row(s)
  - Amazon SFO12 — 18 — Santa Clara County; 265 Lytton Ave  Palo Alto CA 94301 — `page 7, text row at y=434.4`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2025-09-28 .. 2026-12-02

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136306` — event `1605` — tier `exact`

- stored name: `Amazon SFO12`
- stored count **18**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SFO12` — 18 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 18. Amazon (SJC10) (CA)

`warn-ca-2025-10-28-amazon` — currently `not_matched`, stratum `large_census`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-10-28**, effective 2026-01-26..2026-01-26
- **673** affected across 19 published row(s)
  - Amazon (SJC10) — 138 — Santa Clara County; 1120 Enterprise Way  Sunnyvale CA 94089 — `page 7, text row at y=479.8`
  - Amazon (SJC11) — 28 — Santa Clara County; 1100 Enterprise Way  Sunnyvale CA 94089 — `page 7, text row at y=472.2`
  - Amazon (SJC13) — 33 — Santa Clara County; 1160 Enterprise Way  Sunnyvale CA 94089 — `page 7, text row at y=464.6`
  - Amazon (SJC14) — 80 — Santa Clara County; 905 Eleventh Ave  Sunnyvale CA 94089 — `page 7, text row at y=457.1`
  - Amazon (SJC31) — 27 — Santa Clara County; 1100 Discovery Way  Sunnyvale CA 94089 — `page 7, text row at y=449.5`
  - Amazon (SJC32) — 85 — Santa Clara County; 1140 Enterprise Way  Sunnyvale CA 94089 — `page 7, text row at y=442.0`
  - Amazon (SAN 13) — 24 — San Diego County; 10300 Campus Point Dr Ste 200  San Diego CA 92121 — `page 7, text row at y=321.0`
  - Amazon (SAN 15) — 50 — San Diego County; 17075 Camino San Bernardo  San Diego CA 92127 — `page 7, text row at y=313.4`
  - Amazon (SAN 17) — 61 — San Diego County; 4575 La Jolla Village  San Diego CA 92122 — `page 7, text row at y=305.9`
  - Amazon (SAN 18) — 3 — San Diego County; Wework Aventine  San Diego CA 92122 — `page 7, text row at y=298.3`
  - Amazon (SAN 21) — 5 — San Diego County; 4577 La Jolla Village  San Diego CA 92122 — `page 7, text row at y=290.8`
  - Amazon (SAN 3) — 1 — San Diego County; 6971 Otay Mesa Road  San Diego CA 92154 — `page 7, text row at y=283.2`
  - Amazon (SAN 5) — 1 — San Diego County; 7144 Otay Mesa Rd  San Diego CA 92154 — `page 7, text row at y=275.6`
  - Amazon (ONM212) — 3 — San Francisco County; One Embarcadero Center  San Francisco CA 94111 — `page 7, text row at y=260.5`
  - Amazon (ONM213) — 1 — San Francisco County; 110 Sutter  San Francisco CA 94104 — `page 7, text row at y=253.0`
  - Amazon (SFO13) — 41 — San Francisco County; 188 Spear St 2Nd Floor  San Francisco CA 94105 — `page 7, text row at y=245.4`
  - Amazon (SFO19) — 18 — San Francisco County; 350 Bush St  San Francisco CA 94104 — `page 7, text row at y=237.8`
  - Amazon (SFO28) — 71 — San Francisco County; 525 Market St  San Francisco CA 94105 — `page 7, text row at y=230.3`
  - Amazon (SFO38) — 3 — San Francisco County; 660 3Rd St 4Th Floor  San Francisco CA 94107 — `page 7, text row at y=222.7`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2025-09-28 .. 2026-12-02

**92 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136300` — event `1599` — tier `exact`

- stored name: `Amazon (SJC10)`
- stored count **138**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SJC10)` — 138 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `136333` — event `1632` — tier `exact`

- stored name: `Amazon (SFO38)`
- stored count **3**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SFO38)` — 3 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon (SFO38)' differs from the published 'Amazon (SJC10)'

### row `136332` — event `1631` — tier `exact`

- stored name: `Amazon (SFO28)`
- stored count **71**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SFO28)` — 71 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon (SFO28)' differs from the published 'Amazon (SJC10)'

### row `136331` — event `1630` — tier `exact`

- stored name: `Amazon (SFO19)`
- stored count **18**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SFO19)` — 18 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon (SFO19)' differs from the published 'Amazon (SJC10)'

### row `136330` — event `1629` — tier `exact`

- stored name: `Amazon (SFO13)`
- stored count **41**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SFO13)` — 41 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon (SFO13)' differs from the published 'Amazon (SJC10)'

### row `136329` — event `1628` — tier `exact`

- stored name: `Amazon (ONM213)`
- stored count **1**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (ONM213)` — 1 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon (ONM213)' differs from the published 'Amazon (SJC10)'

### row `136328` — event `1627` — tier `exact`

- stored name: `Amazon (ONM212)`
- stored count **3**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (ONM212)` — 3 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon (ONM212)' differs from the published 'Amazon (SJC10)'

### row `136327` — event `1626` — tier `exact`

- stored name: `Amazon (SAN 5)`
- stored count **1**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SAN 5)` — 1 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon (SAN 5)' differs from the published 'Amazon (SJC10)'

### row `136326` — event `1625` — tier `exact`

- stored name: `Amazon (SAN 3)`
- stored count **1**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SAN 3)` — 1 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon (SAN 3)' differs from the published 'Amazon (SJC10)'

### row `136325` — event `1624` — tier `exact`

- stored name: `Amazon (SAN 21)`
- stored count **5**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SAN 21)` — 5 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon (SAN 21)' differs from the published 'Amazon (SJC10)'

### row `136324` — event `1623` — tier `exact`

- stored name: `Amazon (SAN 18)`
- stored count **3**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SAN 18)` — 3 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon (SAN 18)' differs from the published 'Amazon (SJC10)'

### row `136323` — event `1622` — tier `exact`

- stored name: `Amazon (SAN 17)`
- stored count **61**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SAN 17)` — 61 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon (SAN 17)' differs from the published 'Amazon (SJC10)'

### row `136322` — event `1621` — tier `exact`

- stored name: `Amazon (SAN 15)`
- stored count **50**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SAN 15)` — 50 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon (SAN 15)' differs from the published 'Amazon (SJC10)'

### row `136321` — event `1620` — tier `exact`

- stored name: `Amazon (SAN 13)`
- stored count **24**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SAN 13)` — 24 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon (SAN 13)' differs from the published 'Amazon (SJC10)'

### row `136318` — event `1617` — tier `exact`

- stored name: `Amazon SNA18`
- stored count **1**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SNA18` — 1 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon SNA18' differs from the published 'Amazon (SJC10)'

### row `136313` — event `1612` — tier `exact`

- stored name: `Amazon SJC44`
- stored count **18**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SJC44` — 18 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon SJC44' differs from the published 'Amazon (SJC10)'

### row `136312` — event `1611` — tier `exact`

- stored name: `Amazon SJC38`
- stored count **50**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SJC38` — 50 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon SJC38' differs from the published 'Amazon (SJC10)'

### row `136306` — event `1605` — tier `exact`

- stored name: `Amazon SFO12`
- stored count **18**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SFO12` — 18 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon SFO12' differs from the published 'Amazon (SJC10)'

### row `136305` — event `1604` — tier `exact`

- stored name: `Amazon (SJC32)`
- stored count **85**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SJC32)` — 85 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon (SJC32)' differs from the published 'Amazon (SJC10)'

### row `136304` — event `1603` — tier `exact`

- stored name: `Amazon (SJC31)`
- stored count **27**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SJC31)` — 27 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon (SJC31)' differs from the published 'Amazon (SJC10)'

### row `136303` — event `1602` — tier `exact`

- stored name: `Amazon (SJC14)`
- stored count **80**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SJC14)` — 80 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon (SJC14)' differs from the published 'Amazon (SJC10)'

### row `136302` — event `1601` — tier `exact`

- stored name: `Amazon (SJC13)`
- stored count **33**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SJC13)` — 33 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon (SJC13)' differs from the published 'Amazon (SJC10)'

### row `136301` — event `1600` — tier `exact`

- stored name: `Amazon (SJC11)`
- stored count **28**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SJC11)` — 28 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon (SJC11)' differs from the published 'Amazon (SJC10)'

### row `136298` — event `1597` — tier `exact`

- stored name: `Amazon LAX16`
- stored count **3**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon LAX16` — 3 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon LAX16' differs from the published 'Amazon (SJC10)'

### row `135390` — event `1166` — tier `exact`

- stored name: `Amazon - SAN 3`
- stored count **1**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - SAN 3` — 1 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon - SAN 3' differs from the published 'Amazon (SJC10)'

### row `135386` — event `1162` — tier `exact`

- stored name: `Amazon - SAN 15`
- stored count **1**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - SAN 15` — 1 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon - SAN 15' differs from the published 'Amazon (SJC10)'

### row `135382` — event `1158` — tier `exact`

- stored name: `Amazon - SNA 17`
- stored count **1**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - SNA 17` — 1 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon - SNA 17' differs from the published 'Amazon (SJC10)'

### row `135381` — event `1157` — tier `exact`

- stored name: `Amazon - SNA 16`
- stored count **24**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - SNA 16` — 24 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon - SNA 16' differs from the published 'Amazon (SJC10)'

### row `135380` — event `1156` — tier `exact`

- stored name: `Amazon - SNA12`
- stored count **5**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - SNA12` — 5 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon - SNA12' differs from the published 'Amazon (SJC10)'

### row `135374` — event `1150` — tier `exact`

- stored name: `Amazon`
- stored count **3**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon` — 3 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon' differs from the published 'Amazon (SJC10)'

### row `136455` — event `1705` — tier `loose`

- stored name: `Amazon`
- stored count **173**, date `2026-01-06`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon` — 173 — 2026-01-06 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 173 matches neither a component row nor the notice total 673
  - row date is 70 day(s) after the notice date
  - stored name 'Amazon' differs from the published 'Amazon (SJC10)'

### row `136454` — event `1704` — tier `loose`

- stored name: `Amazon`
- stored count **126**, date `2026-01-06`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon` — 126 — 2026-01-06 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 126 matches neither a component row nor the notice total 673
  - row date is 70 day(s) after the notice date
  - stored name 'Amazon' differs from the published 'Amazon (SJC10)'

### row `136453` — event `1703` — tier `loose`

- stored name: `Amazon`
- stored count **107**, date `2026-01-06`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon` — 107 — 2026-01-06 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 107 matches neither a component row nor the notice total 673
  - row date is 70 day(s) after the notice date
  - stored name 'Amazon' differs from the published 'Amazon (SJC10)'

### row `136452` — event `1702` — tier `loose`

- stored name: `Amazon`
- stored count **149**, date `2026-01-06`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon` — 149 — 2026-01-06 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 149 matches neither a component row nor the notice total 673
  - row date is 70 day(s) after the notice date
  - stored name 'Amazon' differs from the published 'Amazon (SJC10)'

### row `136320` — event `1619` — tier `loose`

- stored name: `Amazon SNA3`
- stored count **45**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SNA3` — 45 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 45 matches neither a component row nor the notice total 673
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon SNA3' differs from the published 'Amazon (SJC10)'

### row `136319` — event `1618` — tier `loose`

- stored name: `Amazon SNA19`
- stored count **16**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SNA19` — 16 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 16 matches neither a component row nor the notice total 673
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon SNA19' differs from the published 'Amazon (SJC10)'

### row `136317` — event `1616` — tier `loose`

- stored name: `Amazon SNA17`
- stored count **12**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SNA17` — 12 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 12 matches neither a component row nor the notice total 673
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon SNA17' differs from the published 'Amazon (SJC10)'

### row `136316` — event `1615` — tier `loose`

- stored name: `Amazon SNA16`
- stored count **64**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SNA16` — 64 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 64 matches neither a component row nor the notice total 673
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon SNA16' differs from the published 'Amazon (SJC10)'

### row `136315` — event `1614` — tier `loose`

- stored name: `Amazon SNA12`
- stored count **17**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SNA12` — 17 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 17 matches neither a component row nor the notice total 673
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon SNA12' differs from the published 'Amazon (SJC10)'

### row `136314` — event `1613` — tier `loose`

- stored name: `Amazon SNA11`
- stored count **178**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SNA11` — 178 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 178 matches neither a component row nor the notice total 673
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon SNA11' differs from the published 'Amazon (SJC10)'

### row `136311` — event `1610` — tier `loose`

- stored name: `Amazon SJC25`
- stored count **8**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SJC25` — 8 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 8 matches neither a component row nor the notice total 673
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon SJC25' differs from the published 'Amazon (SJC10)'

### row `136310` — event `1609` — tier `loose`

- stored name: `Amazon SFO39`
- stored count **2**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SFO39` — 2 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 2 matches neither a component row nor the notice total 673
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon SFO39' differs from the published 'Amazon (SJC10)'

### row `136309` — event `1608` — tier `loose`

- stored name: `Amazon SFO36`
- stored count **12**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SFO36` — 12 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 12 matches neither a component row nor the notice total 673
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon SFO36' differs from the published 'Amazon (SJC10)'

### row `136308` — event `1607` — tier `loose`

- stored name: `Amazon SFO24`
- stored count **75**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SFO24` — 75 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 75 matches neither a component row nor the notice total 673
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon SFO24' differs from the published 'Amazon (SJC10)'

### row `136307` — event `1606` — tier `loose`

- stored name: `Amazon SFO22`
- stored count **69**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SFO22` — 69 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 69 matches neither a component row nor the notice total 673
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon SFO22' differs from the published 'Amazon (SJC10)'

### row `136299` — event `1598` — tier `loose`

- stored name: `Amazon LAX78`
- stored count **65**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon LAX78` — 65 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 65 matches neither a component row nor the notice total 673
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon LAX78' differs from the published 'Amazon (SJC10)'

### row `136297` — event `1596` — tier `loose`

- stored name: `Amazon LAX10`
- stored count **62**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon LAX10` — 62 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 62 matches neither a component row nor the notice total 673
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon LAX10' differs from the published 'Amazon (SJC10)'

### row `136296` — event `1595` — tier `loose`

- stored name: `Amazon LAX21`
- stored count **43**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon LAX21` — 43 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 43 matches neither a component row nor the notice total 673
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon LAX21' differs from the published 'Amazon (SJC10)'

### row `136295` — event `1594` — tier `loose`

- stored name: `Amazon LAX22`
- stored count **65**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon LAX22` — 65 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 65 matches neither a component row nor the notice total 673
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon LAX22' differs from the published 'Amazon (SJC10)'

### row `135392` — event `1168` — tier `loose`

- stored name: `Amazon - SFO 28`
- stored count **84**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - SFO 28` — 84 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 84 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon - SFO 28' differs from the published 'Amazon (SJC10)'

### row `135391` — event `1167` — tier `loose`

- stored name: `Amazon - SFO 13`
- stored count **19**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - SFO 13` — 19 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 19 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon - SFO 13' differs from the published 'Amazon (SJC10)'

### row `135389` — event `1165` — tier `loose`

- stored name: `Amazon - SAN 21`
- stored count **2**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - SAN 21` — 2 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 2 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon - SAN 21' differs from the published 'Amazon (SJC10)'

### row `135388` — event `1164` — tier `loose`

- stored name: `Amazon - SAN 18`
- stored count **13**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - SAN 18` — 13 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 13 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon - SAN 18' differs from the published 'Amazon (SJC10)'

### row `135387` — event `1163` — tier `loose`

- stored name: `Amazon - SAN 17`
- stored count **19**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - SAN 17` — 19 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 19 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon - SAN 17' differs from the published 'Amazon (SJC10)'

### row `135385` — event `1161` — tier `loose`

- stored name: `Amazon - SAN 13`
- stored count **38**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - SAN 13` — 38 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 38 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon - SAN 13' differs from the published 'Amazon (SJC10)'

### row `135384` — event `1160` — tier `loose`

- stored name: `Amazon - SNA 3`
- stored count **34**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - SNA 3` — 34 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 34 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon - SNA 3' differs from the published 'Amazon (SJC10)'

### row `135383` — event `1159` — tier `loose`

- stored name: `Amazon - SNA 20`
- stored count **25**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - SNA 20` — 25 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 25 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon - SNA 20' differs from the published 'Amazon (SJC10)'

### row `135379` — event `1155` — tier `loose`

- stored name: `Amazon`
- stored count **89**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon` — 89 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 89 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon' differs from the published 'Amazon (SJC10)'

### row `135378` — event `1154` — tier `loose`

- stored name: `Amazon`
- stored count **81**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon` — 81 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 81 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon' differs from the published 'Amazon (SJC10)'

### row `135377` — event `1153` — tier `loose`

- stored name: `Amazon`
- stored count **87**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon` — 87 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 87 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon' differs from the published 'Amazon (SJC10)'

### row `135376` — event `1152` — tier `loose`

- stored name: `Amazon`
- stored count **58**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon` — 58 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 58 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon' differs from the published 'Amazon (SJC10)'

### row `135375` — event `1151` — tier `loose`

- stored name: `Amazon`
- stored count **11**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon` — 11 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 11 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon' differs from the published 'Amazon (SJC10)'

### row `135373` — event `1149` — tier `loose`

- stored name: `Amazon`
- stored count **32**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon` — 32 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 32 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon' differs from the published 'Amazon (SJC10)'

### row `135372` — event `1148` — tier `loose`

- stored name: `Amazon`
- stored count **72**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon` — 72 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 72 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon' differs from the published 'Amazon (SJC10)'

### row `135371` — event `1147` — tier `loose`

- stored name: `Amazon (SJC44)`
- stored count **49**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SJC44)` — 49 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 49 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon (SJC44)' differs from the published 'Amazon (SJC10)'

### row `135370` — event `1146` — tier `loose`

- stored name: `Amazon (SJC38)`
- stored count **141**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SJC38)` — 141 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 141 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon (SJC38)' differs from the published 'Amazon (SJC10)'

### row `135369` — event `1145` — tier `loose`

- stored name: `Amazon (SJC25)`
- stored count **43**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SJC25)` — 43 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 43 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon (SJC25)' differs from the published 'Amazon (SJC10)'

### row `135368` — event `1144` — tier `loose`

- stored name: `Amazon (LAX78)`
- stored count **45**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (LAX78)` — 45 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 45 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon (LAX78)' differs from the published 'Amazon (SJC10)'

### row `135367` — event `1143` — tier `loose`

- stored name: `Amazon (LAX16)`
- stored count **46**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (LAX16)` — 46 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 46 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon (LAX16)' differs from the published 'Amazon (SJC10)'

### row `135366` — event `1142` — tier `loose`

- stored name: `Amazon (LAX10)`
- stored count **2**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (LAX10)` — 2 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 2 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon (LAX10)' differs from the published 'Amazon (SJC10)'

### row `135365` — event `1141` — tier `loose`

- stored name: `Amazon - MAM7`
- stored count **139**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAM7` — 139 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 139 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon - MAM7' differs from the published 'Amazon (SJC10)'

### row `135364` — event `1140` — tier `loose`

- stored name: `Amazon - MAO6`
- stored count **189**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAO6` — 189 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 189 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon - MAO6' differs from the published 'Amazon (SJC10)'

### row `135363` — event `1139` — tier `loose`

- stored name: `Amazon - MAF5`
- stored count **190**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAF5` — 190 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 190 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon - MAF5' differs from the published 'Amazon (SJC10)'

### row `135362` — event `1138` — tier `loose`

- stored name: `Amazon - MAQ8`
- stored count **163**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAQ8` — 163 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 163 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon - MAQ8' differs from the published 'Amazon (SJC10)'

### row `135361` — event `1137` — tier `loose`

- stored name: `Amazon - MAM9`
- stored count **179**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAM9` — 179 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 179 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon - MAM9' differs from the published 'Amazon (SJC10)'

### row `135360` — event `1136` — tier `loose`

- stored name: `Amazon - MAJ8`
- stored count **160**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAJ8` — 160 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 160 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon - MAJ8' differs from the published 'Amazon (SJC10)'

### row `135359` — event `1135` — tier `loose`

- stored name: `Amazon - MAI8`
- stored count **182**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAI8` — 182 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 182 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon - MAI8' differs from the published 'Amazon (SJC10)'

### row `135358` — event `1134` — tier `loose`

- stored name: `Amazon - MAH8`
- stored count **172**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAH8` — 172 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 172 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon - MAH8' differs from the published 'Amazon (SJC10)'

### row `135357` — event `1133` — tier `loose`

- stored name: `Amazon - MAQ9`
- stored count **174**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAQ9` — 174 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 174 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon - MAQ9' differs from the published 'Amazon (SJC10)'

### row `135356` — event `1132` — tier `loose`

- stored name: `Amazon - MBA6`
- stored count **181**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MBA6` — 181 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 181 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon - MBA6' differs from the published 'Amazon (SJC10)'

### row `135355` — event `1131` — tier `loose`

- stored name: `Amazon - MAC2`
- stored count **175**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAC2` — 175 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 175 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon - MAC2' differs from the published 'Amazon (SJC10)'

### row `135354` — event `1130` — tier `loose`

- stored name: `Amazon - MAB9`
- stored count **191**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAB9` — 191 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 191 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon - MAB9' differs from the published 'Amazon (SJC10)'

### row `135353` — event `1129` — tier `loose`

- stored name: `Amazon - MAB8`
- stored count **191**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAB8` — 191 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 191 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon - MAB8' differs from the published 'Amazon (SJC10)'

### row `135352` — event `1128` — tier `loose`

- stored name: `Amazon - MAK9`
- stored count **134**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAK9` — 134 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 134 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon - MAK9' differs from the published 'Amazon (SJC10)'

### row `135351` — event `1127` — tier `loose`

- stored name: `Amazon - MAG1`
- stored count **185**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAG1` — 185 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 185 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon - MAG1' differs from the published 'Amazon (SJC10)'

### row `135350` — event `1126` — tier `loose`

- stored name: `Amazon - MAF9`
- stored count **155**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAF9` — 155 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 155 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon - MAF9' differs from the published 'Amazon (SJC10)'

### row `135349` — event `1125` — tier `loose`

- stored name: `Amazon - MAF8`
- stored count **196**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAF8` — 196 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 196 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon - MAF8' differs from the published 'Amazon (SJC10)'

### row `135348` — event `1124` — tier `loose`

- stored name: `Amazon - MAF3`
- stored count **201**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAF3` — 201 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 201 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon - MAF3' differs from the published 'Amazon (SJC10)'

### row `135347` — event `1123` — tier `loose`

- stored name: `Amazon - MAC9`
- stored count **168**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAC9` — 168 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 168 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon - MAC9' differs from the published 'Amazon (SJC10)'

### row `135346` — event `1122` — tier `loose`

- stored name: `Amazon - MAB5`
- stored count **184**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAB5` — 184 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 184 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon - MAB5' differs from the published 'Amazon (SJC10)'

### row `135345` — event `1121` — tier `loose`

- stored name: `Amazon - MAB4`
- stored count **131**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAB4` — 131 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 131 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon - MAB4' differs from the published 'Amazon (SJC10)'

### row `135344` — event `1120` — tier `loose`

- stored name: `Amazon - MAB1`
- stored count **215**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAB1` — 215 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 215 matches neither a component row nor the notice total 673
  - row date is 182 day(s) after the notice date
  - stored name 'Amazon - MAB1' differs from the published 'Amazon (SJC10)'

---

## 19. Educational Testing Service (ETS) (CA)

`warn-ca-2025-10-30-educational-testing-service` — currently `not_matched`, stratum `primary`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-10-30**, effective 2025-12-31..2025-12-31
- **757** affected across 1 published row(s)
  - Educational Testing Service (ETS) — 757 — Sacramento County; 1610 R Street, Suite 300  Sacramento CA 95811 — `page 7, text row at y=139.6`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2025-09-30 .. 2026-12-04

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136584` — event `1811` — tier `exact`

- stored name: `Educational Testing Service (ETS)`
- stored count **757**, date `2025-12-31`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Educational Testing Service (ETS)` — 757 — 2025-12-31 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 20. Fresno Economic Opportunities Commission (1101 E. Annandale, 101) (CA)

`warn-ca-2025-10-31-fresno-economic-opportunities-commission` — currently `not_matched`, stratum `large_census`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-10-31**, effective 2026-01-01..2026-01-01
- **639** affected across 41 published row(s)
  - Fresno Economic Opportunities Commission (1101 E. Annandale, 101) — 6 — Fresno County; 1101 E. Annandale, 101  Sanger CA 93657 — `page 7, text row at y=94.2`
  - Fresno Economic Opportunities Commission (112 - 4th St.) — 7 — Fresno County; 112 - 4th St.  Orange Cove CA 93646 — `page 7, text row at y=86.6`
  - Fresno Economic Opportunities Commission (115 W. Belmont Ave) — 3 — Fresno County; 115 W. Belmont Ave  Mendota CA 93640 — `page 7, text row at y=79.1`
  - Fresno Economic Opportunities Commission (1189 Martin St) — 2 — Fresno County; 1189 Martin St  Fresno CA 93706 — `page 7, text row at y=71.5`
  - Fresno Economic Opportunities Commission (1189 Martin St) — 33 — Fresno County; 1189 Martin St.  Fresno CA 93706 — `page 7, text row at y=64.0`
  - Fresno Economic Opportunities Commission (1240 E. Washington) — 14 — Fresno County; 1240 E. Washington  Reedley CA 93654 — `page 7, text row at y=56.4`
  - Fresno Economic Opportunities Commission (1325 Stillman St.) — 4 — Fresno County; 1325 Stillman St.  Selma CA 93662 — `page 7, text row at y=48.8`
  - Fresno Economic Opportunities Commission (1350 E. Annadale) — 7 — Fresno County; 1350 E. Annadale  Fresno CA 93706 — `page 7, text row at y=41.3`
  - Fresno Economic Opportunities Commission (13660 E. Manning Ave) — 7 — Fresno County; 13660 E. Manning Ave  Parlier CA 93648 — `page 7, text row at y=33.7`
  - Fresno Economic Opportunities Commission (1420 Second St.) — 4 — Fresno County; 1420 Second St.  Selma CA 93662 — `page 8, text row at y=600.7`
  - Fresno Economic Opportunities Commission (1441 Divisadero) — 17 — Fresno County; 1441 Divisadero  Fresno CA 93721 — `page 8, text row at y=593.2`
  - Fresno Economic Opportunities Commission (1504 N. Webser) — 9 — Fresno County; 1504 N. Weber  Fresno CA 93728 — `page 8, text row at y=585.6`
  - Fresno Economic Opportunities Commission (1620 W. Fairmont) — 19 — Fresno County; 1620 W. Fairmont  Fresno CA 93705 — `page 8, text row at y=578.0`
  - Fresno Economic Opportunities Commission (16641 Palmer St.) — 10 — Fresno County; 16641 Palmer St.  Huron CA 93234 — `page 8, text row at y=570.5`
  - Fresno Economic Opportunities Commission (1701 Alton St.) — 9 — Fresno County; 1701 Alton St.  Selma CA 93662 — `page 8, text row at y=562.9`
  - Fresno Economic Opportunities Commission (1920 Mariposa Street) — 263 — Fresno County; 1920 Mariposa Street  Fresno CA 93721 — `page 8, text row at y=555.4`
  - Fresno Economic Opportunities Commission (2063 S. Cedar Ave) — 8 — Fresno County; 2063 S. Cedar Ave  Fresno CA 93702 — `page 8, text row at y=547.8`
  - Fresno Economic Opportunities Commission (2117 W. McKinley Ave) — 8 — Fresno County; 2117 W. McKinley Ave  Fresno CA 93726 — `page 8, text row at y=540.2`
  - Fresno Economic Opportunities Commission (2121 N. Van Ness Ave) — 9 — Fresno County; 2121 N. Van Ness Ave  Fresno CA 93704 — `page 8, text row at y=532.7`
  - Fresno Economic Opportunities Commission (2420 W. Clemenceau Ave) — 5 — Fresno County; 2420 W. Clemenceau Ave  Caruthers CA 93609 — `page 8, text row at y=525.1`
  - Fresno Economic Opportunities Commission (2529 Willow Ave) — 5 — Fresno County; 2529 Willow Ave  Clovis CA 93612 — `page 8, text row at y=517.6`
  - Fresno Economic Opportunities Commission (2751 Fig Street) — 7 — Fresno County; 2751 Fig Street  Selma CA 93662 — `page 8, text row at y=510.0`
  - Fresno Economic Opportunities Commission (295 W. Tuft St) — 9 — Fresno County; 295 W. Tuft St  Mendota CA 93640 — `page 8, text row at y=502.4`
  - Fresno Economic Opportunities Commission (3037 S. Orchid Ave) — 12 — Fresno County; 3037 S. Orchid Ave  Sanger CA 93657 — `page 8, text row at y=494.9`
  - Fresno Economic Opportunities Commission (3110 W. Nielsen) — 4 — Fresno County; 3110 W. Nielsen  Fresno CA 93706 — `page 8, text row at y=487.3`
  - Fresno Economic Opportunities Commission (3257 E. Shields Ave) — 12 — Fresno County; 3257 E. Shields Ave  Fresno CA 93726 — `page 8, text row at y=479.8`
  - Fresno Economic Opportunities Commission (388 S. Brawley Ave) — 8 — Fresno County; 388 S. Brawley Ave  Fresno CA 93706 — `page 8, text row at y=472.2`
  - Fresno Economic Opportunities Commission (4156 E. Dakota Ave) — 28 — Fresno County; 4156 E. Dakota Ave  Fresno CA 93726 — `page 8, text row at y=464.6`
  - Fresno Economic Opportunities Commission (4273 W. Richert, Ave, 107) — 15 — Fresno County; 4273 W. Richert, Ave, 107  Fresno CA 93722 — `page 8, text row at y=457.1`
  - Fresno Economic Opportunities Commission (4856 E. Cesar Chavez Blvd) — 15 — Fresno County; 4856 E. Cesar Chavez Blvd  Fresno CA 93727 — `page 8, text row at y=449.5`
  - Fresno Economic Opportunities Commission (4995 E. Balch Ave) — 18 — Fresno County; 4995 E. Balch Ave  Fresno CA 93727 — `page 8, text row at y=442.0`
  - Fresno Economic Opportunities Commission (510 Barstow Ave) — 4 — Fresno County; 510 Barstow Ave  Clovis CA 93612 — `page 8, text row at y=434.4`
  - Fresno Economic Opportunities Commission (5104 N. West) — 11 — Fresno County; 5104 N. West  Fresno CA 93711 — `page 8, text row at y=426.8`
  - Fresno Economic Opportunities Commission (5244 E. Pine Ave) — 5 — Fresno County; 5244 E. Pine Ave  Fresno CA 93727 — `page 8, text row at y=419.3`
  - Fresno Economic Opportunities Commission (5550 N. Fresno St) — 8 — Fresno County; 5550 N. Fresno St  Fresno CA 93710 — `page 8, text row at y=411.7`
  - Fresno Economic Opportunities Commission (710 N. Hughes Ave) — 8 — Fresno County; 710 N. Hughes Ave  Fresno CA 93728 — `page 8, text row at y=404.2`
  - Fresno Economic Opportunities Commission (7171 N. Sugarpine Ave) — 4 — Fresno County; 7171 N. Sugarpine Ave  Pinedale CA 96350 — `page 8, text row at y=396.6`
  - Fresno Economic Opportunities Commission (719 S. Madera Ave) — 4 — Fresno County; 719 S. Madera Ave  Kerman CA 93630 — `page 8, text row at y=389.0`
  - Fresno Economic Opportunities Commission (745 N. First St) — 4 — Fresno County; 745 N. First St  Fresno CA 93702 — `page 8, text row at y=381.5`
  - Fresno Economic Opportunities Commission (788 W. Shaw Ave) — 10 — Fresno County; 788 W. Shaw Ave  Clovis CA 93612 — `page 8, text row at y=373.9`
  - Fresno Economic Opportunities Commission (8535 S 9th Street) — 4 — Fresno County; 8535 S 9th Street  San Joaquin CA 93660 — `page 8, text row at y=366.4`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2025-10-01 .. 2026-12-05

**41 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136516` — event `1750` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission (1101 E. Annandale, 101)`
- stored count **6**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission (1101 E. Annandale, 101)` — 6 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `136556` — event `1790` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission`
- stored count **4**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission` — 4 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)'

### row `136555` — event `1789` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission`
- stored count **10**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission` — 10 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)'

### row `136554` — event `1788` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission`
- stored count **4**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission` — 4 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)'

### row `136553` — event `1787` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission`
- stored count **4**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission` — 4 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)'

### row `136552` — event `1786` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission`
- stored count **4**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission` — 4 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)'

### row `136551` — event `1785` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission`
- stored count **8**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission` — 8 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)'

### row `136550` — event `1784` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission`
- stored count **8**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission` — 8 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)'

### row `136549` — event `1783` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission`
- stored count **5**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission` — 5 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)'

### row `136548` — event `1782` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission (5104 N. West)`
- stored count **11**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission (5104 N. West)` — 11 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Fresno Economic Opportunities Commission (5104 N. West)' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)'

### row `136547` — event `1781` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission`
- stored count **4**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission` — 4 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)'

### row `136546` — event `1780` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission`
- stored count **18**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission` — 18 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)'

### row `136545` — event `1779` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission`
- stored count **15**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission` — 15 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)'

### row `136544` — event `1778` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission (4273 W. Richert, Ave, 107)`
- stored count **15**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission (4273 W. Richert, Ave, 107)` — 15 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Fresno Economic Opportunities Commission (4273 W. Richert, Ave, 107)' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)'

### row `136543` — event `1777` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission`
- stored count **28**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission` — 28 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)'

### row `136542` — event `1776` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission`
- stored count **8**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission` — 8 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)'

### row `136541` — event `1775` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission`
- stored count **12**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission` — 12 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)'

### row `136540` — event `1774` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission (3110 W. Nielsen)`
- stored count **4**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission (3110 W. Nielsen)` — 4 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Fresno Economic Opportunities Commission (3110 W. Nielsen)' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)'

### row `136539` — event `1773` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission`
- stored count **12**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission` — 12 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)'

### row `136538` — event `1772` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission`
- stored count **9**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission` — 9 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)'

### row `136537` — event `1771` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission`
- stored count **7**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission` — 7 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)'

### row `136536` — event `1770` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission`
- stored count **5**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission` — 5 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)'

### row `136535` — event `1769` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission`
- stored count **5**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission` — 5 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)'

### row `136534` — event `1768` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission`
- stored count **9**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission` — 9 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)'

### row `136533` — event `1767` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission`
- stored count **8**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission` — 8 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)'

### row `136532` — event `1766` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission`
- stored count **8**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission` — 8 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)'

### row `136531` — event `1765` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission`
- stored count **263**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission` — 263 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)'

### row `136530` — event `1764` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission`
- stored count **9**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission` — 9 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)'

### row `136529` — event `1763` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission`
- stored count **10**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission` — 10 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)'

### row `136528` — event `1762` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission (1620 W. Fairmont)`
- stored count **19**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission (1620 W. Fairmont)` — 19 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Fresno Economic Opportunities Commission (1620 W. Fairmont)' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)'

### row `136527` — event `1761` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission (1504 N. Webser)`
- stored count **9**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission (1504 N. Webser)` — 9 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Fresno Economic Opportunities Commission (1504 N. Webser)' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)'

### row `136526` — event `1760` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission (1441 Divisadero)`
- stored count **17**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission (1441 Divisadero)` — 17 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Fresno Economic Opportunities Commission (1441 Divisadero)' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)'

### row `136525` — event `1759` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission`
- stored count **4**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission` — 4 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)'

### row `136524` — event `1758` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission`
- stored count **7**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission` — 7 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)'

### row `136523` — event `1757` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission (1350 E. Annadale)`
- stored count **7**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission (1350 E. Annadale)` — 7 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Fresno Economic Opportunities Commission (1350 E. Annadale)' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)'

### row `136522` — event `1756` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission`
- stored count **4**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission` — 4 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)'

### row `136521` — event `1755` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission (1240 E. Washington)`
- stored count **14**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission (1240 E. Washington)` — 14 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Fresno Economic Opportunities Commission (1240 E. Washington)' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)'

### row `136520` — event `1754` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission`
- stored count **33**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission` — 33 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)'

### row `136519` — event `1753` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission`
- stored count **2**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission` — 2 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)'

### row `136518` — event `1752` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission`
- stored count **3**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission` — 3 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)'

### row `136517` — event `1751` — tier `exact`

- stored name: `Fresno Economic Opportunities Commission`
- stored count **7**, date `2026-01-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Fresno Economic Opportunities Commission` — 7 — 2026-01-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Fresno Economic Opportunities Commission' differs from the published 'Fresno Economic Opportunities Commission (1101 E. Annandale, 101)'

---

## 21. Mattel, Inc. (CA)

`warn-ca-2025-11-13-mattel` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-11-13**, effective 2026-01-12..2026-01-12
- **89** affected across 1 published row(s)
  - Mattel, Inc. — 89 — Los Angeles County; 333 Continental Blvd  El Segundo CA 90245 — `page 9, text row at y=343.7`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2025-10-14 .. 2026-12-18

**2 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136421` — event `1684` — tier `exact`

- stored name: `Mattel, Inc.`
- stored count **89**, date `2026-01-12`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Mattel, Inc.` — 89 — 2026-01-12 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `135083` — event `983` — tier `loose`

- stored name: `Mattel, Inc.`
- stored count **65**, date `2026-05-22`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Mattel, Inc.` — 65 — 2026-05-22 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 65 matches neither a component row nor the notice total 89
  - row date is 190 day(s) after the notice date

---

## 22. Terzo Enterprises Incorporated (CA)

`warn-ca-2025-12-01-terzo-enterprises-incorporated` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-12-01**, effective 2026-01-30..2026-01-30
- **58** affected across 1 published row(s)
  - Terzo Enterprises Incorporated — 58 — Kern County; 19254 Quinn Road  Bakersfield CA 93308 — `page 10, text row at y=502.4`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2025-11-01 .. 2027-01-05

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136246` — event `1582` — tier `exact`

- stored name: `Terzo Enterprises Incorporated`
- stored count **58**, date `2026-01-30`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Terzo Enterprises Incorporated` — 58 — 2026-01-30 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 23. Wabash National LP (CA)

`warn-ca-2026-01-05-wabash-national` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-01-05**, effective 2026-03-06..2026-03-06
- **100** affected across 2 published row(s)
  - Wabash National LP — 6 — Riverside County; 1190 Harley Knox Blvd.  Perris CA 92571 — `page 10, text row at y=169.8`
  - Wabash National LP — 94 — Riverside County; 22135 Alessandro Blvd  Moreno Valley CA 92553 — `page 10, text row at y=162.2`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2025-12-06 .. 2027-02-09

**2 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135967` — event `1467` — tier `exact`

- stored name: `Wabash National LP`
- stored count **94**, date `2026-03-06`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Wabash National LP` — 94 — 2026-03-06 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `135966` — event `1466` — tier `exact`

- stored name: `Wabash National LP`
- stored count **6**, date `2026-03-06`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Wabash National LP` — 6 — 2026-03-06 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 24. Autodesk (CA)

`warn-ca-2026-01-23-autodesk` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-01-23**, effective 2026-04-01..2026-04-01
- **104** affected across 1 published row(s)
  - Autodesk — 104 — San Francisco County; 1 Market Street  San Francisco CA 94105 — `page 11, text row at y=532.7`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2025-12-24 .. 2027-02-27

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135682` — event `1318` — tier `exact`

- stored name: `Autodesk`
- stored count **104**, date `2026-04-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Autodesk` — 104 — 2026-04-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 25. Amazon - MAB1 (CA)

`warn-ca-2026-01-28-amazon` — currently `not_matched`, stratum `large_census`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-01-28**, effective 2026-04-28..2026-04-28
- **3,855** affected across 22 published row(s)
  - Amazon - MAB1 — 215 — Los Angeles County; 6245 Topanga Canyon Blvd.  Woodland Hills CA 91367 — `page 11, text row at y=389.0`
  - Amazon - MAB4 — 131 — Los Angeles County; 5101 Lankershim Blvd.  North Hollywood CA 91601 — `page 11, text row at y=381.5`
  - Amazon - MAB5 — 184 — Los Angeles County; 19340 Rinaldi St.  Porter Ranch CA 91326 — `page 11, text row at y=373.9`
  - Amazon - MAC9 — 168 — Los Angeles County; 6235 E Spring St.  Long Beach CA 90808 — `page 11, text row at y=366.4`
  - Amazon - MAF3 — 201 — Los Angeles County; 16325 Ventura Blvd.  Encino CA 91436 — `page 11, text row at y=358.8`
  - Amazon - MAF8 — 196 — Los Angeles County; 21035 Hawthrone Blvd.  Torrance CA 90503 — `page 11, text row at y=351.2`
  - Amazon - MAF9 — 155 — Los Angeles County; 11340 South St.  Cerritos CA 90703 — `page 11, text row at y=343.7`
  - Amazon - MAG1 — 185 — Los Angeles County; 6855 S La Cienega Blvd  Los Angeles CA 90045 — `page 11, text row at y=336.1`
  - Amazon - MAK9 — 134 — Los Angeles County; 3425 E. Colorado Blvd.  Pasadena CA 91107 — `page 11, text row at y=328.6`
  - Amazon - MAB8 — 191 — Orange County; 6911 Warner Avenue  Huntington Beach CA 92647 — `page 11, text row at y=321.0`
  - Amazon - MAB9 — 191 — Orange County; 13672 Jamboree Rd.  Irvine CA 92602 — `page 11, text row at y=313.4`
  - Amazon - MAC2 — 175 — Orange County; 1100 S. Harbor Blvd.  Fullerton CA 92832 — `page 11, text row at y=305.9`
  - Amazon - MBA6 — 181 — Orange County; 18100 Brookhurst St.  Fountain Valley CA 92708 — `page 11, text row at y=298.3`
  - Amazon - MAQ9 — 174 — Placer County; 6780 Stanford Ranch Rd.  Roseville CA 95678 — `page 11, text row at y=290.8`
  - Amazon - MAH8 — 172 — Riverside County; 40481 Murrieta Hot Springs Rd.  Murrieta CA 92563 — `page 11, text row at y=283.2`
  - Amazon - MAI8 — 182 — Riverside County; 14837 Pomerado Rd.  Poway CA 92064 — `page 11, text row at y=275.6`
  - Amazon - MAJ8 — 160 — Riverside County; 3941 Bedford Canyon Rd.  Corona CA 92883 — `page 11, text row at y=268.1`
  - Amazon - MAM9 — 179 — Sacramento County; 7530 Elk Grove Blvd.  Elk Grove CA 95757 — `page 11, text row at y=260.5`
  - Amazon - MAQ8 — 163 — Sacramento County; 5425 Sunrise Blvd.  Citrus Heights CA 95610 — `page 11, text row at y=253.0`
  - Amazon - MAF5 — 190 — San Bernardino County; 235 E. Foothill Blvd.  Upland CA 91786 — `page 11, text row at y=245.4`
  - Amazon - MAO6 — 189 — San Bernardino County; 16188 South Highland Ave.  Fontana CA 92336 — `page 11, text row at y=237.8`
  - Amazon - MAM7 — 139 — Ventura County; 742 Los Angeles Ave  Moorpark CA 93021 — `page 11, text row at y=230.3`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2025-12-29 .. 2027-03-04

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135344` — event `1120` — tier `exact`

- stored name: `Amazon - MAB1`
- stored count **215**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAB1` — 215 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 26. Amazon (LAX10) (CA)

`warn-ca-2026-01-29-amazon` — currently `not_matched`, stratum `large_census`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-01-29**, effective 2026-04-28..2026-04-28
- **1,025** affected across 27 published row(s)
  - Amazon (LAX10) — 2 — Los Angeles County; 1620 26Th St Ste 4000N  Santa Monica CA 90404 — `page 11, text row at y=169.8`
  - Amazon (LAX16) — 46 — Los Angeles County; 2425 Olympic Blvd Ste 2000E  Santa Monica CA 90404 — `page 11, text row at y=162.2`
  - Amazon (LAX78) — 45 — Los Angeles County; 2450 Colorado Avenue  Santa Monica CA 90404 — `page 11, text row at y=154.7`
  - Amazon (SJC25) — 43 — Santa Clara County; 2795 Augustine Dr  Santa Clara CA 95054 — `page 11, text row at y=124.4`
  - Amazon (SJC38) — 141 — Santa Clara County; 3075 Olcott St  Santa Clara CA 95054 — `page 11, text row at y=116.9`
  - Amazon (SJC44) — 49 — Santa Clara County; 4980 Great America Pkwy  Santa Clara CA 95054 — `page 11, text row at y=109.3`
  - Amazon — 72 — Santa Clara County; 401 San Antonio Rd  Mountain View CA 94040 — `page 11, text row at y=101.8`
  - Amazon — 32 — Santa Clara County; 1120 Enterprise Way  Sunnyvale CA 94089 — `page 11, text row at y=94.2`
  - Amazon — 3 — Santa Clara County; 1100 Enterprise Way  Sunnyvale CA 94089 — `page 11, text row at y=86.6`
  - Amazon — 11 — Santa Clara County; 1160 Enterprise Way  Sunnyvale CA 94089 — `page 11, text row at y=79.1`
  - Amazon — 58 — Santa Clara County; 905 Eleventh Ave.  Sunnyvale CA 94089 — `page 11, text row at y=71.5`
  - Amazon — 87 — Santa Clara County; 1100 Discovery Way  Sunnyvale CA 94089 — `page 11, text row at y=64.0`
  - Amazon — 81 — Santa Clara County; 1140 Enterprise Way  Sunnyvale CA 94089 — `page 11, text row at y=56.4`
  - Amazon — 89 — Santa Clara County; 2100 University Ave  East Palo Alto CA 94303 — `page 11, text row at y=48.8`
  - Amazon - SNA12 — 5 — Orange County; 20 Pacifica Ste 900  Irvine CA 92618 — `page 11, text row at y=41.3`
  - Amazon - SNA 16 — 24 — Orange County; 17300 Laguna Canyon Rd.  Irvine CA 92618 — `page 11, text row at y=33.7`
  - Amazon - SNA 17 — 1 — Orange County; 140 Progress 200  Irvine CA 92618 — `page 12, text row at y=600.7`
  - Amazon - SNA 20 — 25 — Orange County; 200 Spectrum Center Dr.  Irvine CA 92618 — `page 12, text row at y=593.2`
  - Amazon - SNA 3 — 34 — Orange County; 40 Pacifica Ste. 100  Irvine CA 92618 — `page 12, text row at y=585.6`
  - Amazon - SAN 13 — 38 — San Diego County; 10300 Campus Point Dr. Ste. 200  San Diego CA 92121 — `page 12, text row at y=578.0`
  - Amazon - SAN 15 — 1 — San Diego County; 17075 Camino San Bernardo  San Diego CA 92127 — `page 12, text row at y=570.5`
  - Amazon - SAN 17 — 19 — San Diego County; 4575 La Jolla Village  San Diego CA 92122 — `page 12, text row at y=562.9`
  - Amazon - SAN 18 — 13 — San Diego County; Wework Aventine  San Diego CA 92122 — `page 12, text row at y=555.4`
  - Amazon - SAN 21 — 2 — San Diego County; 4577 La Jolla Village  San Diego CA 92122 — `page 12, text row at y=547.8`
  - Amazon - SAN 3 — 1 — San Diego County; 6971 Otay Mesa Road  San Diego CA 92154 — `page 12, text row at y=540.2`
  - Amazon - SFO 13 — 19 — San Francisco County; 188 Spear St. 2nd Floor  San Francisco CA 94105 — `page 12, text row at y=532.7`
  - Amazon - SFO 28 — 84 — San Francisco County; 525 Market St.  San Francisco CA 94105 — `page 12, text row at y=525.1`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2025-12-30 .. 2027-03-05

**92 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135366` — event `1142` — tier `exact`

- stored name: `Amazon (LAX10)`
- stored count **2**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (LAX10)` — 2 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `136333` — event `1632` — tier `exact`

- stored name: `Amazon (SFO38)`
- stored count **3**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SFO38)` — 3 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is -3 day(s) after the notice date
  - stored name 'Amazon (SFO38)' differs from the published 'Amazon (LAX10)'

### row `136329` — event `1628` — tier `exact`

- stored name: `Amazon (ONM213)`
- stored count **1**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (ONM213)` — 1 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is -3 day(s) after the notice date
  - stored name 'Amazon (ONM213)' differs from the published 'Amazon (LAX10)'

### row `136328` — event `1627` — tier `exact`

- stored name: `Amazon (ONM212)`
- stored count **3**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (ONM212)` — 3 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is -3 day(s) after the notice date
  - stored name 'Amazon (ONM212)' differs from the published 'Amazon (LAX10)'

### row `136327` — event `1626` — tier `exact`

- stored name: `Amazon (SAN 5)`
- stored count **1**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SAN 5)` — 1 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is -3 day(s) after the notice date
  - stored name 'Amazon (SAN 5)' differs from the published 'Amazon (LAX10)'

### row `136326` — event `1625` — tier `exact`

- stored name: `Amazon (SAN 3)`
- stored count **1**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SAN 3)` — 1 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is -3 day(s) after the notice date
  - stored name 'Amazon (SAN 3)' differs from the published 'Amazon (LAX10)'

### row `136325` — event `1624` — tier `exact`

- stored name: `Amazon (SAN 21)`
- stored count **5**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SAN 21)` — 5 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is -3 day(s) after the notice date
  - stored name 'Amazon (SAN 21)' differs from the published 'Amazon (LAX10)'

### row `136324` — event `1623` — tier `exact`

- stored name: `Amazon (SAN 18)`
- stored count **3**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SAN 18)` — 3 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is -3 day(s) after the notice date
  - stored name 'Amazon (SAN 18)' differs from the published 'Amazon (LAX10)'

### row `136321` — event `1620` — tier `exact`

- stored name: `Amazon (SAN 13)`
- stored count **24**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SAN 13)` — 24 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is -3 day(s) after the notice date
  - stored name 'Amazon (SAN 13)' differs from the published 'Amazon (LAX10)'

### row `136320` — event `1619` — tier `exact`

- stored name: `Amazon SNA3`
- stored count **45**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SNA3` — 45 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is -3 day(s) after the notice date
  - stored name 'Amazon SNA3' differs from the published 'Amazon (LAX10)'

### row `136318` — event `1617` — tier `exact`

- stored name: `Amazon SNA18`
- stored count **1**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SNA18` — 1 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is -3 day(s) after the notice date
  - stored name 'Amazon SNA18' differs from the published 'Amazon (LAX10)'

### row `136310` — event `1609` — tier `exact`

- stored name: `Amazon SFO39`
- stored count **2**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SFO39` — 2 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is -3 day(s) after the notice date
  - stored name 'Amazon SFO39' differs from the published 'Amazon (LAX10)'

### row `136298` — event `1597` — tier `exact`

- stored name: `Amazon LAX16`
- stored count **3**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon LAX16` — 3 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is -3 day(s) after the notice date
  - stored name 'Amazon LAX16' differs from the published 'Amazon (LAX10)'

### row `136296` — event `1595` — tier `exact`

- stored name: `Amazon LAX21`
- stored count **43**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon LAX21` — 43 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is -3 day(s) after the notice date
  - stored name 'Amazon LAX21' differs from the published 'Amazon (LAX10)'

### row `135392` — event `1168` — tier `exact`

- stored name: `Amazon - SFO 28`
- stored count **84**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - SFO 28` — 84 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon - SFO 28' differs from the published 'Amazon (LAX10)'

### row `135391` — event `1167` — tier `exact`

- stored name: `Amazon - SFO 13`
- stored count **19**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - SFO 13` — 19 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon - SFO 13' differs from the published 'Amazon (LAX10)'

### row `135390` — event `1166` — tier `exact`

- stored name: `Amazon - SAN 3`
- stored count **1**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - SAN 3` — 1 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon - SAN 3' differs from the published 'Amazon (LAX10)'

### row `135389` — event `1165` — tier `exact`

- stored name: `Amazon - SAN 21`
- stored count **2**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - SAN 21` — 2 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon - SAN 21' differs from the published 'Amazon (LAX10)'

### row `135388` — event `1164` — tier `exact`

- stored name: `Amazon - SAN 18`
- stored count **13**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - SAN 18` — 13 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon - SAN 18' differs from the published 'Amazon (LAX10)'

### row `135387` — event `1163` — tier `exact`

- stored name: `Amazon - SAN 17`
- stored count **19**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - SAN 17` — 19 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon - SAN 17' differs from the published 'Amazon (LAX10)'

### row `135386` — event `1162` — tier `exact`

- stored name: `Amazon - SAN 15`
- stored count **1**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - SAN 15` — 1 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon - SAN 15' differs from the published 'Amazon (LAX10)'

### row `135385` — event `1161` — tier `exact`

- stored name: `Amazon - SAN 13`
- stored count **38**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - SAN 13` — 38 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon - SAN 13' differs from the published 'Amazon (LAX10)'

### row `135384` — event `1160` — tier `exact`

- stored name: `Amazon - SNA 3`
- stored count **34**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - SNA 3` — 34 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon - SNA 3' differs from the published 'Amazon (LAX10)'

### row `135383` — event `1159` — tier `exact`

- stored name: `Amazon - SNA 20`
- stored count **25**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - SNA 20` — 25 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon - SNA 20' differs from the published 'Amazon (LAX10)'

### row `135382` — event `1158` — tier `exact`

- stored name: `Amazon - SNA 17`
- stored count **1**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - SNA 17` — 1 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon - SNA 17' differs from the published 'Amazon (LAX10)'

### row `135381` — event `1157` — tier `exact`

- stored name: `Amazon - SNA 16`
- stored count **24**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - SNA 16` — 24 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon - SNA 16' differs from the published 'Amazon (LAX10)'

### row `135380` — event `1156` — tier `exact`

- stored name: `Amazon - SNA12`
- stored count **5**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - SNA12` — 5 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon - SNA12' differs from the published 'Amazon (LAX10)'

### row `135379` — event `1155` — tier `exact`

- stored name: `Amazon`
- stored count **89**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon` — 89 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon' differs from the published 'Amazon (LAX10)'

### row `135378` — event `1154` — tier `exact`

- stored name: `Amazon`
- stored count **81**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon` — 81 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon' differs from the published 'Amazon (LAX10)'

### row `135377` — event `1153` — tier `exact`

- stored name: `Amazon`
- stored count **87**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon` — 87 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon' differs from the published 'Amazon (LAX10)'

### row `135376` — event `1152` — tier `exact`

- stored name: `Amazon`
- stored count **58**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon` — 58 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon' differs from the published 'Amazon (LAX10)'

### row `135375` — event `1151` — tier `exact`

- stored name: `Amazon`
- stored count **11**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon` — 11 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon' differs from the published 'Amazon (LAX10)'

### row `135374` — event `1150` — tier `exact`

- stored name: `Amazon`
- stored count **3**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon` — 3 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon' differs from the published 'Amazon (LAX10)'

### row `135373` — event `1149` — tier `exact`

- stored name: `Amazon`
- stored count **32**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon` — 32 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon' differs from the published 'Amazon (LAX10)'

### row `135372` — event `1148` — tier `exact`

- stored name: `Amazon`
- stored count **72**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon` — 72 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon' differs from the published 'Amazon (LAX10)'

### row `135371` — event `1147` — tier `exact`

- stored name: `Amazon (SJC44)`
- stored count **49**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SJC44)` — 49 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon (SJC44)' differs from the published 'Amazon (LAX10)'

### row `135370` — event `1146` — tier `exact`

- stored name: `Amazon (SJC38)`
- stored count **141**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SJC38)` — 141 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon (SJC38)' differs from the published 'Amazon (LAX10)'

### row `135369` — event `1145` — tier `exact`

- stored name: `Amazon (SJC25)`
- stored count **43**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SJC25)` — 43 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon (SJC25)' differs from the published 'Amazon (LAX10)'

### row `135368` — event `1144` — tier `exact`

- stored name: `Amazon (LAX78)`
- stored count **45**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (LAX78)` — 45 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon (LAX78)' differs from the published 'Amazon (LAX10)'

### row `135367` — event `1143` — tier `exact`

- stored name: `Amazon (LAX16)`
- stored count **46**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (LAX16)` — 46 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon (LAX16)' differs from the published 'Amazon (LAX10)'

### row `136455` — event `1705` — tier `loose`

- stored name: `Amazon`
- stored count **173**, date `2026-01-06`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon` — 173 — 2026-01-06 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 173 matches neither a component row nor the notice total 1025
  - row date is -23 day(s) after the notice date
  - stored name 'Amazon' differs from the published 'Amazon (LAX10)'

### row `136454` — event `1704` — tier `loose`

- stored name: `Amazon`
- stored count **126**, date `2026-01-06`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon` — 126 — 2026-01-06 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 126 matches neither a component row nor the notice total 1025
  - row date is -23 day(s) after the notice date
  - stored name 'Amazon' differs from the published 'Amazon (LAX10)'

### row `136453` — event `1703` — tier `loose`

- stored name: `Amazon`
- stored count **107**, date `2026-01-06`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon` — 107 — 2026-01-06 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 107 matches neither a component row nor the notice total 1025
  - row date is -23 day(s) after the notice date
  - stored name 'Amazon' differs from the published 'Amazon (LAX10)'

### row `136452` — event `1702` — tier `loose`

- stored name: `Amazon`
- stored count **149**, date `2026-01-06`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon` — 149 — 2026-01-06 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 149 matches neither a component row nor the notice total 1025
  - row date is -23 day(s) after the notice date
  - stored name 'Amazon' differs from the published 'Amazon (LAX10)'

### row `136332` — event `1631` — tier `loose`

- stored name: `Amazon (SFO28)`
- stored count **71**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SFO28)` — 71 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 71 matches neither a component row nor the notice total 1025
  - row date is -3 day(s) after the notice date
  - stored name 'Amazon (SFO28)' differs from the published 'Amazon (LAX10)'

### row `136331` — event `1630` — tier `loose`

- stored name: `Amazon (SFO19)`
- stored count **18**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SFO19)` — 18 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 18 matches neither a component row nor the notice total 1025
  - row date is -3 day(s) after the notice date
  - stored name 'Amazon (SFO19)' differs from the published 'Amazon (LAX10)'

### row `136330` — event `1629` — tier `loose`

- stored name: `Amazon (SFO13)`
- stored count **41**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SFO13)` — 41 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 41 matches neither a component row nor the notice total 1025
  - row date is -3 day(s) after the notice date
  - stored name 'Amazon (SFO13)' differs from the published 'Amazon (LAX10)'

### row `136323` — event `1622` — tier `loose`

- stored name: `Amazon (SAN 17)`
- stored count **61**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SAN 17)` — 61 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 61 matches neither a component row nor the notice total 1025
  - row date is -3 day(s) after the notice date
  - stored name 'Amazon (SAN 17)' differs from the published 'Amazon (LAX10)'

### row `136322` — event `1621` — tier `loose`

- stored name: `Amazon (SAN 15)`
- stored count **50**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SAN 15)` — 50 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 50 matches neither a component row nor the notice total 1025
  - row date is -3 day(s) after the notice date
  - stored name 'Amazon (SAN 15)' differs from the published 'Amazon (LAX10)'

### row `136319` — event `1618` — tier `loose`

- stored name: `Amazon SNA19`
- stored count **16**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SNA19` — 16 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 16 matches neither a component row nor the notice total 1025
  - row date is -3 day(s) after the notice date
  - stored name 'Amazon SNA19' differs from the published 'Amazon (LAX10)'

### row `136317` — event `1616` — tier `loose`

- stored name: `Amazon SNA17`
- stored count **12**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SNA17` — 12 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 12 matches neither a component row nor the notice total 1025
  - row date is -3 day(s) after the notice date
  - stored name 'Amazon SNA17' differs from the published 'Amazon (LAX10)'

### row `136316` — event `1615` — tier `loose`

- stored name: `Amazon SNA16`
- stored count **64**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SNA16` — 64 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 64 matches neither a component row nor the notice total 1025
  - row date is -3 day(s) after the notice date
  - stored name 'Amazon SNA16' differs from the published 'Amazon (LAX10)'

### row `136315` — event `1614` — tier `loose`

- stored name: `Amazon SNA12`
- stored count **17**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SNA12` — 17 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 17 matches neither a component row nor the notice total 1025
  - row date is -3 day(s) after the notice date
  - stored name 'Amazon SNA12' differs from the published 'Amazon (LAX10)'

### row `136314` — event `1613` — tier `loose`

- stored name: `Amazon SNA11`
- stored count **178**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SNA11` — 178 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 178 matches neither a component row nor the notice total 1025
  - row date is -3 day(s) after the notice date
  - stored name 'Amazon SNA11' differs from the published 'Amazon (LAX10)'

### row `136313` — event `1612` — tier `loose`

- stored name: `Amazon SJC44`
- stored count **18**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SJC44` — 18 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 18 matches neither a component row nor the notice total 1025
  - row date is -3 day(s) after the notice date
  - stored name 'Amazon SJC44' differs from the published 'Amazon (LAX10)'

### row `136312` — event `1611` — tier `loose`

- stored name: `Amazon SJC38`
- stored count **50**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SJC38` — 50 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 50 matches neither a component row nor the notice total 1025
  - row date is -3 day(s) after the notice date
  - stored name 'Amazon SJC38' differs from the published 'Amazon (LAX10)'

### row `136311` — event `1610` — tier `loose`

- stored name: `Amazon SJC25`
- stored count **8**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SJC25` — 8 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 8 matches neither a component row nor the notice total 1025
  - row date is -3 day(s) after the notice date
  - stored name 'Amazon SJC25' differs from the published 'Amazon (LAX10)'

### row `136309` — event `1608` — tier `loose`

- stored name: `Amazon SFO36`
- stored count **12**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SFO36` — 12 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 12 matches neither a component row nor the notice total 1025
  - row date is -3 day(s) after the notice date
  - stored name 'Amazon SFO36' differs from the published 'Amazon (LAX10)'

### row `136308` — event `1607` — tier `loose`

- stored name: `Amazon SFO24`
- stored count **75**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SFO24` — 75 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 75 matches neither a component row nor the notice total 1025
  - row date is -3 day(s) after the notice date
  - stored name 'Amazon SFO24' differs from the published 'Amazon (LAX10)'

### row `136307` — event `1606` — tier `loose`

- stored name: `Amazon SFO22`
- stored count **69**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SFO22` — 69 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 69 matches neither a component row nor the notice total 1025
  - row date is -3 day(s) after the notice date
  - stored name 'Amazon SFO22' differs from the published 'Amazon (LAX10)'

### row `136306` — event `1605` — tier `loose`

- stored name: `Amazon SFO12`
- stored count **18**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon SFO12` — 18 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 18 matches neither a component row nor the notice total 1025
  - row date is -3 day(s) after the notice date
  - stored name 'Amazon SFO12' differs from the published 'Amazon (LAX10)'

### row `136305` — event `1604` — tier `loose`

- stored name: `Amazon (SJC32)`
- stored count **85**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SJC32)` — 85 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 85 matches neither a component row nor the notice total 1025
  - row date is -3 day(s) after the notice date
  - stored name 'Amazon (SJC32)' differs from the published 'Amazon (LAX10)'

### row `136304` — event `1603` — tier `loose`

- stored name: `Amazon (SJC31)`
- stored count **27**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SJC31)` — 27 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 27 matches neither a component row nor the notice total 1025
  - row date is -3 day(s) after the notice date
  - stored name 'Amazon (SJC31)' differs from the published 'Amazon (LAX10)'

### row `136303` — event `1602` — tier `loose`

- stored name: `Amazon (SJC14)`
- stored count **80**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SJC14)` — 80 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 80 matches neither a component row nor the notice total 1025
  - row date is -3 day(s) after the notice date
  - stored name 'Amazon (SJC14)' differs from the published 'Amazon (LAX10)'

### row `136302` — event `1601` — tier `loose`

- stored name: `Amazon (SJC13)`
- stored count **33**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SJC13)` — 33 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 33 matches neither a component row nor the notice total 1025
  - row date is -3 day(s) after the notice date
  - stored name 'Amazon (SJC13)' differs from the published 'Amazon (LAX10)'

### row `136301` — event `1600` — tier `loose`

- stored name: `Amazon (SJC11)`
- stored count **28**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SJC11)` — 28 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 28 matches neither a component row nor the notice total 1025
  - row date is -3 day(s) after the notice date
  - stored name 'Amazon (SJC11)' differs from the published 'Amazon (LAX10)'

### row `136300` — event `1599` — tier `loose`

- stored name: `Amazon (SJC10)`
- stored count **138**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon (SJC10)` — 138 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 138 matches neither a component row nor the notice total 1025
  - row date is -3 day(s) after the notice date
  - stored name 'Amazon (SJC10)' differs from the published 'Amazon (LAX10)'

### row `136299` — event `1598` — tier `loose`

- stored name: `Amazon LAX78`
- stored count **65**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon LAX78` — 65 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 65 matches neither a component row nor the notice total 1025
  - row date is -3 day(s) after the notice date
  - stored name 'Amazon LAX78' differs from the published 'Amazon (LAX10)'

### row `136297` — event `1596` — tier `loose`

- stored name: `Amazon LAX10`
- stored count **62**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon LAX10` — 62 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 62 matches neither a component row nor the notice total 1025
  - row date is -3 day(s) after the notice date
  - stored name 'Amazon LAX10' differs from the published 'Amazon (LAX10)'

### row `136295` — event `1594` — tier `loose`

- stored name: `Amazon LAX22`
- stored count **65**, date `2026-01-26`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon LAX22` — 65 — 2026-01-26 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 65 matches neither a component row nor the notice total 1025
  - row date is -3 day(s) after the notice date
  - stored name 'Amazon LAX22' differs from the published 'Amazon (LAX10)'

### row `135365` — event `1141` — tier `loose`

- stored name: `Amazon - MAM7`
- stored count **139**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAM7` — 139 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 139 matches neither a component row nor the notice total 1025
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon - MAM7' differs from the published 'Amazon (LAX10)'

### row `135364` — event `1140` — tier `loose`

- stored name: `Amazon - MAO6`
- stored count **189**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAO6` — 189 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 189 matches neither a component row nor the notice total 1025
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon - MAO6' differs from the published 'Amazon (LAX10)'

### row `135363` — event `1139` — tier `loose`

- stored name: `Amazon - MAF5`
- stored count **190**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAF5` — 190 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 190 matches neither a component row nor the notice total 1025
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon - MAF5' differs from the published 'Amazon (LAX10)'

### row `135362` — event `1138` — tier `loose`

- stored name: `Amazon - MAQ8`
- stored count **163**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAQ8` — 163 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 163 matches neither a component row nor the notice total 1025
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon - MAQ8' differs from the published 'Amazon (LAX10)'

### row `135361` — event `1137` — tier `loose`

- stored name: `Amazon - MAM9`
- stored count **179**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAM9` — 179 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 179 matches neither a component row nor the notice total 1025
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon - MAM9' differs from the published 'Amazon (LAX10)'

### row `135360` — event `1136` — tier `loose`

- stored name: `Amazon - MAJ8`
- stored count **160**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAJ8` — 160 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 160 matches neither a component row nor the notice total 1025
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon - MAJ8' differs from the published 'Amazon (LAX10)'

### row `135359` — event `1135` — tier `loose`

- stored name: `Amazon - MAI8`
- stored count **182**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAI8` — 182 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 182 matches neither a component row nor the notice total 1025
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon - MAI8' differs from the published 'Amazon (LAX10)'

### row `135358` — event `1134` — tier `loose`

- stored name: `Amazon - MAH8`
- stored count **172**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAH8` — 172 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 172 matches neither a component row nor the notice total 1025
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon - MAH8' differs from the published 'Amazon (LAX10)'

### row `135357` — event `1133` — tier `loose`

- stored name: `Amazon - MAQ9`
- stored count **174**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAQ9` — 174 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 174 matches neither a component row nor the notice total 1025
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon - MAQ9' differs from the published 'Amazon (LAX10)'

### row `135356` — event `1132` — tier `loose`

- stored name: `Amazon - MBA6`
- stored count **181**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MBA6` — 181 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 181 matches neither a component row nor the notice total 1025
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon - MBA6' differs from the published 'Amazon (LAX10)'

### row `135355` — event `1131` — tier `loose`

- stored name: `Amazon - MAC2`
- stored count **175**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAC2` — 175 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 175 matches neither a component row nor the notice total 1025
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon - MAC2' differs from the published 'Amazon (LAX10)'

### row `135354` — event `1130` — tier `loose`

- stored name: `Amazon - MAB9`
- stored count **191**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAB9` — 191 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 191 matches neither a component row nor the notice total 1025
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon - MAB9' differs from the published 'Amazon (LAX10)'

### row `135353` — event `1129` — tier `loose`

- stored name: `Amazon - MAB8`
- stored count **191**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAB8` — 191 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 191 matches neither a component row nor the notice total 1025
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon - MAB8' differs from the published 'Amazon (LAX10)'

### row `135352` — event `1128` — tier `loose`

- stored name: `Amazon - MAK9`
- stored count **134**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAK9` — 134 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 134 matches neither a component row nor the notice total 1025
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon - MAK9' differs from the published 'Amazon (LAX10)'

### row `135351` — event `1127` — tier `loose`

- stored name: `Amazon - MAG1`
- stored count **185**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAG1` — 185 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 185 matches neither a component row nor the notice total 1025
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon - MAG1' differs from the published 'Amazon (LAX10)'

### row `135350` — event `1126` — tier `loose`

- stored name: `Amazon - MAF9`
- stored count **155**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAF9` — 155 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 155 matches neither a component row nor the notice total 1025
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon - MAF9' differs from the published 'Amazon (LAX10)'

### row `135349` — event `1125` — tier `loose`

- stored name: `Amazon - MAF8`
- stored count **196**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAF8` — 196 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 196 matches neither a component row nor the notice total 1025
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon - MAF8' differs from the published 'Amazon (LAX10)'

### row `135348` — event `1124` — tier `loose`

- stored name: `Amazon - MAF3`
- stored count **201**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAF3` — 201 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 201 matches neither a component row nor the notice total 1025
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon - MAF3' differs from the published 'Amazon (LAX10)'

### row `135347` — event `1123` — tier `loose`

- stored name: `Amazon - MAC9`
- stored count **168**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAC9` — 168 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 168 matches neither a component row nor the notice total 1025
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon - MAC9' differs from the published 'Amazon (LAX10)'

### row `135346` — event `1122` — tier `loose`

- stored name: `Amazon - MAB5`
- stored count **184**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAB5` — 184 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 184 matches neither a component row nor the notice total 1025
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon - MAB5' differs from the published 'Amazon (LAX10)'

### row `135345` — event `1121` — tier `loose`

- stored name: `Amazon - MAB4`
- stored count **131**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAB4` — 131 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 131 matches neither a component row nor the notice total 1025
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon - MAB4' differs from the published 'Amazon (LAX10)'

### row `135344` — event `1120` — tier `loose`

- stored name: `Amazon - MAB1`
- stored count **215**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Amazon - MAB1` — 215 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 215 matches neither a component row nor the notice total 1025
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon - MAB1' differs from the published 'Amazon (LAX10)'

---

## 27. Del Monte Foods Corporation II Inc - Modesto (CA)

`warn-ca-2026-01-30-del-monte-foods-ii` — currently `not_matched`, stratum `large_census`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-01-30**, effective 2026-04-07..2026-04-07
- **776** affected across 2 published row(s)
  - Del Monte Foods Corporation II Inc - Modesto — 765 — Stanislaus County; 4000 Yosemite Boulevard  Modesto CA 95357 — `page 12, text row at y=230.3`
  - Del Monte Foods Corporation II Inc. - Hughson — 11 — Stanislaus County; 2018 Santa Fe Avenue  Hughson CA 95326 — `page 12, text row at y=222.7`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2025-12-31 .. 2027-03-06

**4 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135621` — event `1282` — tier `exact`

- stored name: `Del Monte Foods Corporation II Inc - Modesto`
- stored count **765**, date `2026-04-07`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Del Monte Foods Corporation II Inc - Modesto` — 765 — 2026-04-07 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `135622` — event `1283` — tier `exact`

- stored name: `Del Monte Foods Corporation II Inc. - Hughson`
- stored count **11**, date `2026-04-07`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Del Monte Foods Corporation II Inc. - Hughson` — 11 — 2026-04-07 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Del Monte Foods Corporation II Inc. - Hughson' differs from the published 'Del Monte Foods Corporation II Inc - Modesto'

### row `135625` — event `1286` — tier `loose`

- stored name: `Del Monte Foods Corporation II Inc.`
- stored count **25**, date `2026-04-07`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Del Monte Foods Corporation II Inc.` — 25 — 2026-04-07 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 25 matches neither a component row nor the notice total 776
  - row date equals this notice's earliest published effective date
  - stored name 'Del Monte Foods Corporation II Inc.' differs from the published 'Del Monte Foods Corporation II Inc - Modesto'

### row `135264` — event `1083` — tier `loose`

- stored name: `Del Monte Foods Corporation II Inc.`
- stored count **21**, date `2026-05-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Del Monte Foods Corporation II Inc.` — 21 — 2026-05-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 21 matches neither a component row nor the notice total 776
  - row date is 91 day(s) after the notice date
  - stored name 'Del Monte Foods Corporation II Inc.' differs from the published 'Del Monte Foods Corporation II Inc - Modesto'

---

## 28. First Brands Group, LLC (CA)

`warn-ca-2026-02-03-first-brands` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-02-03**, effective 2026-04-04..2026-04-04
- **98** affected across 1 published row(s)
  - First Brands Group, LLC — 98 — Stanislaus County; 2701 Keystone Pkwy  Patterson CA 95363 — `page 12, text row at y=351.2`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2026-01-04 .. 2027-03-10

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135649` — event `1297` — tier `exact`

- stored name: `First Brands Group, LLC`
- stored count **98**, date `2026-04-04`, state `CA`, source `warn` / `CA WARN notice`
- live now: `First Brands Group, LLC` — 98 — 2026-04-04 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 29. Raley's (CA)

`warn-ca-2026-02-20-raley-s` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-02-20**, effective 2026-04-28..2026-04-28
- **43** affected across 1 published row(s)
  - Raley's — 43 — Contra Costa County; 3632 Lone Tree Way  Antioch CA 94509 — `page 13, text row at y=373.9`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2026-01-21 .. 2027-03-27

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135393` — event `1169` — tier `exact`

- stored name: `Raley's`
- stored count **43**, date `2026-04-28`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Raley's` — 43 — 2026-04-28 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 30. KBR Services LLC (CA)

`warn-ca-2026-03-06-kbr-services` — currently `not_matched`, stratum `primary`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-03-06**, effective 2026-05-06..2026-05-06
- **758** affected across 1 published row(s)
  - KBR Services LLC — 758 — San Bernardino County; Bldg. 896, Langford Lake Road  Fort Irwin CA 92311 — `page 13, text row at y=41.3`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2026-02-04 .. 2027-04-10

**2 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135210` — event `1064` — tier `exact`

- stored name: `KBR Services LLC`
- stored count **758**, date `2026-05-06`, state `CA`, source `warn` / `CA WARN notice`
- live now: `KBR Services LLC` — 758 — 2026-05-06 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `134247` — event `483` — tier `loose`

- stored name: `KBR Services LLC`
- stored count **650**, date `2026-08-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `KBR Services LLC` — 650 — 2026-08-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 650 matches neither a component row nor the notice total 758
  - row date is 148 day(s) after the notice date

---

## 31. MAG Brand Group, LLC (CA)

`warn-ca-2026-03-25-mag-brand` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-03-25**, effective 2026-08-01..2026-08-01
- **53** affected across 1 published row(s)
  - MAG Brand Group, LLC — 53 — Los Angeles County; 13861 Rosecrans Avenue  Santa Fe Springs CA 90670 — `page 14, text row at y=64.0`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2026-02-23 .. 2027-04-29

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `134246` — event `482` — tier `exact`

- stored name: `MAG Brand Group, LLC`
- stored count **53**, date `2026-08-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `MAG Brand Group, LLC` — 53 — 2026-08-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 32. Oracle America, Inc. (CA)

`warn-ca-2026-04-01-oracle-america` — currently `not_matched`, stratum `large_census`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-04-01**, effective 2026-06-01..2026-06-01
- **702** affected across 4 published row(s)
  - Oracle America, Inc. — 158 — Alameda County; 5815 Owens Drive  Pleasanton CA 94588 — `page 15, text row at y=313.4`
  - Oracle America, Inc. — 50 — Los Angeles County; 1620 26th Street, Suite 100S  Santa Monica CA 90404 — `page 15, text row at y=298.3`
  - Oracle America, Inc. — 310 — San Mateo County; 500 Oracle Parkway  Redwood City CA 94065 — `page 15, text row at y=290.8`
  - Oracle America, Inc. — 184 — Santa Clara County; 4230 Leonard Stocking Drive  Santa Clara CA 95054 — `page 15, text row at y=283.2`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2026-03-02 .. 2027-05-06

**4 candidate row(s).** Each block below is one row and says nothing about any other.

### row `134962` — event `913` — tier `exact`

- stored name: `Oracle America, Inc.`
- stored count **184**, date `2026-06-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Oracle America, Inc.` — 184 — 2026-06-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `134961` — event `912` — tier `exact`

- stored name: `Oracle America, Inc.`
- stored count **310**, date `2026-06-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Oracle America, Inc.` — 310 — 2026-06-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `134960` — event `911` — tier `exact`

- stored name: `Oracle America, Inc.`
- stored count **50**, date `2026-06-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Oracle America, Inc.` — 50 — 2026-06-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `134958` — event `909` — tier `exact`

- stored name: `Oracle America, Inc.`
- stored count **158**, date `2026-06-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Oracle America, Inc.` — 158 — 2026-06-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 33. Wellpath and CFMG - South Placer Jail (CA)

`warn-ca-2026-04-07-wellpath-and-cfmg` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-04-07**, effective 2026-06-30..2026-06-30
- **89** affected across 3 published row(s)
  - Wellpath and CFMG - South Placer Jail — 35 — Placer County; 11801 Go For Broke Rd.  Roseville CA 95678 — `page 16, text row at y=578.0`
  - Wellpath and CFMG - Placer Jail - Auburn — 50 — Placer County; 2775 Richardson Dr.  Auburn CA 95603 — `page 16, text row at y=570.5`
  - Wellpath and CFMG - Placer Juvi Detention — 4 — Placer County; 11260 B Ave.  Auburn CA 95603 — `page 16, text row at y=562.9`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2026-03-08 .. 2027-05-12

**3 candidate row(s).** Each block below is one row and says nothing about any other.

### row `134537` — event `661` — tier `exact`

- stored name: `Wellpath and CFMG - South Placer Jail`
- stored count **35**, date `2026-06-30`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Wellpath and CFMG - South Placer Jail` — 35 — 2026-06-30 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `134539` — event `663` — tier `exact`

- stored name: `Wellpath and CFMG - Placer Juvi Detention`
- stored count **4**, date `2026-06-30`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Wellpath and CFMG - Placer Juvi Detention` — 4 — 2026-06-30 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Wellpath and CFMG - Placer Juvi Detention' differs from the published 'Wellpath and CFMG - South Placer Jail'

### row `134538` — event `662` — tier `exact`

- stored name: `Wellpath and CFMG - Placer Jail - Auburn`
- stored count **50**, date `2026-06-30`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Wellpath and CFMG - Placer Jail - Auburn` — 50 — 2026-06-30 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Wellpath and CFMG - Placer Jail - Auburn' differs from the published 'Wellpath and CFMG - South Placer Jail'

---

## 34. YMCA Juan Pacifico Ontiveros Elementary School (CA)

`warn-ca-2026-04-17-ymca-juan-pacifico-ontiveros` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-04-17**, effective 2026-06-09..2026-06-09
- **10** affected across 1 published row(s)
  - YMCA Juan Pacifico Ontiveros Elementary School — 10 — Santa Barbara County; 930 Rancho Verde  Santa Maria CA 93458 — `page 16, text row at y=101.8`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2026-03-18 .. 2027-05-22

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `134867` — event `855` — tier `exact`

- stored name: `YMCA Juan Pacifico Ontiveros Elementary School`
- stored count **10**, date `2026-06-09`, state `CA`, source `warn` / `CA WARN notice`
- live now: `YMCA Juan Pacifico Ontiveros Elementary School` — 10 — 2026-06-09 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 35. Geodis (CA)

`warn-ca-2026-04-28-geodis` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-04-28**, effective 2026-07-03..2026-07-03
- **238** affected across 1 published row(s)
  - Geodis — 238 — San Bernardino County; 1710 West Baseline Road  Rialto CA 92376 — `page 17, text row at y=184.9`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2026-03-29 .. 2027-06-02

**2 candidate row(s).** Each block below is one row and says nothing about any other.

### row `134477` — event `617` — tier `exact`

- stored name: `Geodis`
- stored count **238**, date `2026-07-03`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Geodis` — 238 — 2026-07-03 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `134037` — event `43966` — tier `loose`

- stored name: `GEODIS`
- stored count **81**, date `2026-09-03`, state `CA`, source `warn` / `CA WARN notice`
- live now: `GEODIS` — 81 — 2026-09-03 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 81 matches neither a component row nor the notice total 238
  - row date is 128 day(s) after the notice date

---

## 36. Boys & Girls Club at the LA Harbor - Narbonne High School (CA)

`warn-ca-2026-05-13-boys-girls-club-at` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-05-13**, effective 2026-06-10..2026-06-10
- **2** affected across 1 published row(s)
  - Boys & Girls Club at the LA Harbor - Narbonne High School — 2 — Los Angeles County; 243000 S. Western Ave.  Harbor City CA 90710 — `page 18, text row at y=426.8`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2026-04-13 .. 2027-06-17

**17 candidate row(s).** Each block below is one row and says nothing about any other.

### row `134852` — event `843` — tier `exact`

- stored name: `Boys & Girls Club at the LA Harbor - Narbonne High School`
- stored count **2**, date `2026-06-10`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Boys & Girls Club at the LA Harbor - Narbonne High School` — 2 — 2026-06-10 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `134851` — event `842` — tier `loose`

- stored name: `Boys &Girls Club of the La Harbor - Harbor City Elementary School`
- stored count **10**, date `2026-06-10`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Boys &Girls Club of the La Harbor - Harbor City Elementary School` — 10 — 2026-06-10 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 10 matches neither a component row nor the notice total 2
  - row date equals this notice's earliest published effective date
  - stored name 'Boys &Girls Club of the La Harbor - Harbor City Elementary School' differs from the published 'Boys & Girls Club at the LA Harbor - Narbonne High School'

### row `134850` — event `841` — tier `loose`

- stored name: `Boys & Girls Club of the LA Harbor - Fleming Middle School`
- stored count **7**, date `2026-06-10`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Boys & Girls Club of the LA Harbor - Fleming Middle School` — 7 — 2026-06-10 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 7 matches neither a component row nor the notice total 2
  - row date equals this notice's earliest published effective date
  - stored name 'Boys & Girls Club of the LA Harbor - Fleming Middle School' differs from the published 'Boys & Girls Club at the LA Harbor - Narbonne High School'

### row `134849` — event `840` — tier `loose`

- stored name: `Boys & Girls Club of the LA Harbor - Environmental Charter MS`
- stored count **4**, date `2026-06-10`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Boys & Girls Club of the LA Harbor - Environmental Charter MS` — 4 — 2026-06-10 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 4 matches neither a component row nor the notice total 2
  - row date equals this notice's earliest published effective date
  - stored name 'Boys & Girls Club of the LA Harbor - Environmental Charter MS' differs from the published 'Boys & Girls Club at the LA Harbor - Narbonne High School'

### row `134848` — event `839` — tier `loose`

- stored name: `Boys & Girls Club of the La Harbor - Cheryl Green/Torrance Club`
- stored count **1**, date `2026-06-10`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Boys & Girls Club of the La Harbor - Cheryl Green/Torrance Club` — 1 — 2026-06-10 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 1 matches neither a component row nor the notice total 2
  - row date equals this notice's earliest published effective date
  - stored name 'Boys & Girls Club of the La Harbor - Cheryl Green/Torrance Club' differs from the published 'Boys & Girls Club at the LA Harbor - Narbonne High School'

### row `134846` — event `837` — tier `loose`

- stored name: `Boys & Girls Club of the LA Harbor - Taper Ave. Elementary`
- stored count **8**, date `2026-06-10`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Boys & Girls Club of the LA Harbor - Taper Ave. Elementary` — 8 — 2026-06-10 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 8 matches neither a component row nor the notice total 2
  - row date equals this notice's earliest published effective date
  - stored name 'Boys & Girls Club of the LA Harbor - Taper Ave. Elementary' differs from the published 'Boys & Girls Club at the LA Harbor - Narbonne High School'

### row `134845` — event `836` — tier `loose`

- stored name: `Boys & Girls Club of the LA Harbor - South Shores Elementary`
- stored count **3**, date `2026-06-10`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Boys & Girls Club of the LA Harbor - South Shores Elementary` — 3 — 2026-06-10 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 3 matches neither a component row nor the notice total 2
  - row date equals this notice's earliest published effective date
  - stored name 'Boys & Girls Club of the LA Harbor - South Shores Elementary' differs from the published 'Boys & Girls Club at the LA Harbor - Narbonne High School'

### row `134844` — event `835` — tier `loose`

- stored name: `Boys & Girls Club of LA Harbor - Point Fermin Elementary`
- stored count **5**, date `2026-06-10`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Boys & Girls Club of LA Harbor - Point Fermin Elementary` — 5 — 2026-06-10 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 5 matches neither a component row nor the notice total 2
  - row date equals this notice's earliest published effective date
  - stored name 'Boys & Girls Club of LA Harbor - Point Fermin Elementary' differs from the published 'Boys & Girls Club at the LA Harbor - Narbonne High School'

### row `134843` — event `834` — tier `loose`

- stored name: `Boys & Girls Club of the LA Harbor - Park Western Elementary`
- stored count **8**, date `2026-06-10`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Boys & Girls Club of the LA Harbor - Park Western Elementary` — 8 — 2026-06-10 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 8 matches neither a component row nor the notice total 2
  - row date equals this notice's earliest published effective date
  - stored name 'Boys & Girls Club of the LA Harbor - Park Western Elementary' differs from the published 'Boys & Girls Club at the LA Harbor - Narbonne High School'

### row `134842` — event `833` — tier `loose`

- stored name: `Boys & Girls Club of the LA Harbor - Dana Middle School`
- stored count **3**, date `2026-06-10`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Boys & Girls Club of the LA Harbor - Dana Middle School` — 3 — 2026-06-10 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 3 matches neither a component row nor the notice total 2
  - row date equals this notice's earliest published effective date
  - stored name 'Boys & Girls Club of the LA Harbor - Dana Middle School' differs from the published 'Boys & Girls Club at the LA Harbor - Narbonne High School'

### row `134841` — event `832` — tier `loose`

- stored name: `Boys & Girls Club of the LA Harbor - Barton Hill Elementary`
- stored count **3**, date `2026-06-10`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Boys & Girls Club of the LA Harbor - Barton Hill Elementary` — 3 — 2026-06-10 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 3 matches neither a component row nor the notice total 2
  - row date equals this notice's earliest published effective date
  - stored name 'Boys & Girls Club of the LA Harbor - Barton Hill Elementary' differs from the published 'Boys & Girls Club at the LA Harbor - Narbonne High School'

### row `134840` — event `831` — tier `loose`

- stored name: `Boys & Girls Club of LA Harbor - Wilmington Park ES`
- stored count **3**, date `2026-06-10`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Boys & Girls Club of LA Harbor - Wilmington Park ES` — 3 — 2026-06-10 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 3 matches neither a component row nor the notice total 2
  - row date equals this notice's earliest published effective date
  - stored name 'Boys & Girls Club of LA Harbor - Wilmington Park ES' differs from the published 'Boys & Girls Club at the LA Harbor - Narbonne High School'

### row `134839` — event `830` — tier `loose`

- stored name: `Boys & Girls Club of the LA Harbor - Wilmington Club`
- stored count **3**, date `2026-06-10`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Boys & Girls Club of the LA Harbor - Wilmington Club` — 3 — 2026-06-10 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 3 matches neither a component row nor the notice total 2
  - row date equals this notice's earliest published effective date
  - stored name 'Boys & Girls Club of the LA Harbor - Wilmington Club' differs from the published 'Boys & Girls Club at the LA Harbor - Narbonne High School'

### row `134838` — event `829` — tier `loose`

- stored name: `Boys & Girls Club of the LA Harbor - Harbor Teacher Prep Academy`
- stored count **7**, date `2026-06-10`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Boys & Girls Club of the LA Harbor - Harbor Teacher Prep Academy` — 7 — 2026-06-10 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 7 matches neither a component row nor the notice total 2
  - row date equals this notice's earliest published effective date
  - stored name 'Boys & Girls Club of the LA Harbor - Harbor Teacher Prep Academy' differs from the published 'Boys & Girls Club at the LA Harbor - Narbonne High School'

### row `134837` — event `828` — tier `loose`

- stored name: `Boys & Girls Club of LA Harbor - Harry Bridges Span School`
- stored count **3**, date `2026-06-10`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Boys & Girls Club of LA Harbor - Harry Bridges Span School` — 3 — 2026-06-10 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 3 matches neither a component row nor the notice total 2
  - row date equals this notice's earliest published effective date
  - stored name 'Boys & Girls Club of LA Harbor - Harry Bridges Span School' differs from the published 'Boys & Girls Club at the LA Harbor - Narbonne High School'

### row `134836` — event `827` — tier `loose`

- stored name: `Boys & Girls Club of the LA Harbor - Gulf Ave Elementary`
- stored count **1**, date `2026-06-10`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Boys & Girls Club of the LA Harbor - Gulf Ave Elementary` — 1 — 2026-06-10 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 1 matches neither a component row nor the notice total 2
  - row date equals this notice's earliest published effective date
  - stored name 'Boys & Girls Club of the LA Harbor - Gulf Ave Elementary' differs from the published 'Boys & Girls Club at the LA Harbor - Narbonne High School'

### row `134834` — event `825` — tier `loose`

- stored name: `Boys & Girls Club of the LA Harbor - Banning High`
- stored count **5**, date `2026-06-10`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Boys & Girls Club of the LA Harbor - Banning High` — 5 — 2026-06-10 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 5 matches neither a component row nor the notice total 2
  - row date equals this notice's earliest published effective date
  - stored name 'Boys & Girls Club of the LA Harbor - Banning High' differs from the published 'Boys & Girls Club at the LA Harbor - Narbonne High School'

---

## 37. LinkedIn Corporation (CA)

`warn-ca-2026-05-15-linkedin` — currently `not_matched`, stratum `large_census`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-05-15**, effective 2026-07-13..2026-07-13
- **606** affected across 5 published row(s)
  - LinkedIn Corporation — 108 — San Francisco County; 222 Second Street  San Francisco CA 94105 — `page 18, text row at y=396.6`
  - LinkedIn Corporation — 21 — Santa Barbara County; 6410 Via Real  Carpinteria CA 93013 — `page 18, text row at y=389.0`
  - LinkedIn Corporation — 59 — Santa Clara County; 1000 W. Maude Avenue  Sunnyvale CA 94085 — `page 18, text row at y=381.5`
  - LinkedIn Corporation — 352 — Santa Clara County; 700 E. Middlefield Road  Mountain View CA 94043 — `page 18, text row at y=373.9`
  - LinkedIn Corporation (Home Office) — 66 — Santa Clara County; Home Office  Mountain View CA 94043 — `page 18, text row at y=366.4`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2026-04-15 .. 2027-06-19

**5 candidate row(s).** Each block below is one row and says nothing about any other.

### row `134428` — event `590` — tier `exact`

- stored name: `LinkedIn Corporation`
- stored count **352**, date `2026-07-13`, state `CA`, source `warn` / `CA WARN notice`
- live now: `LinkedIn Corporation` — 352 — 2026-07-13 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `134427` — event `589` — tier `exact`

- stored name: `LinkedIn Corporation`
- stored count **59**, date `2026-07-13`, state `CA`, source `warn` / `CA WARN notice`
- live now: `LinkedIn Corporation` — 59 — 2026-07-13 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `134426` — event `588` — tier `exact`

- stored name: `LinkedIn Corporation`
- stored count **21**, date `2026-07-13`, state `CA`, source `warn` / `CA WARN notice`
- live now: `LinkedIn Corporation` — 21 — 2026-07-13 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `134425` — event `587` — tier `exact`

- stored name: `LinkedIn Corporation`
- stored count **108**, date `2026-07-13`, state `CA`, source `warn` / `CA WARN notice`
- live now: `LinkedIn Corporation` — 108 — 2026-07-13 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `134429` — event `591` — tier `exact`

- stored name: `LinkedIn Corporation (Home Office)`
- stored count **66**, date `2026-07-13`, state `CA`, source `warn` / `CA WARN notice`
- live now: `LinkedIn Corporation (Home Office)` — 66 — 2026-07-13 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'LinkedIn Corporation (Home Office)' differs from the published 'LinkedIn Corporation'

---

## 38. TeamOne (CA)

`warn-ca-2026-05-18-teamone` — currently `not_matched`, stratum `large_census`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-05-18**, effective 2026-06-13..2026-06-13
- **725** affected across 1 published row(s)
  - TeamOne — 725 — Riverside County; 29800 Eucalyptus Ave.  Moreno Valley CA 92555 — `page 18, text row at y=305.9`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2026-04-18 .. 2027-06-22

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `134797` — event `804` — tier `exact`

- stored name: `TeamOne`
- stored count **725**, date `2026-06-13`, state `CA`, source `warn` / `CA WARN notice`
- live now: `TeamOne` — 725 — 2026-06-13 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 39. Intuit Inc. (CA)

`warn-ca-2026-05-20-intuit` — currently `not_matched`, stratum `large_census`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-05-20**, effective 2026-07-31..2026-07-31
- **910** affected across 4 published row(s)
  - Intuit Inc. — 493 — Santa Clara County; 2601 Garcia Avenue  Mountain View CA 94043 — `page 18, text row at y=162.2`
  - Intuit Inc. — 90 — Los Angeles County; 21650 Oxnard Street  Woodland Hills CA 91367 — `page 18, text row at y=139.6`
  - Intuit Inc. — 277 — San Diego County; 7535 Torry Santa Fe Rd.  San Diego CA 92129 — `page 18, text row at y=132.0`
  - Intuit Inc. — 50 — San Francisco County; 505 Howard St.  San Francisco CA 94105 — `page 18, text row at y=124.4`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2026-04-20 .. 2027-06-24

**4 candidate row(s).** Each block below is one row and says nothing about any other.

### row `134259` — event `491` — tier `exact`

- stored name: `Intuit Inc.`
- stored count **50**, date `2026-07-31`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Intuit Inc.` — 50 — 2026-07-31 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `134258` — event `490` — tier `exact`

- stored name: `Intuit Inc.`
- stored count **277**, date `2026-07-31`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Intuit Inc.` — 277 — 2026-07-31 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `134257` — event `489` — tier `exact`

- stored name: `Intuit Inc.`
- stored count **90**, date `2026-07-31`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Intuit Inc.` — 90 — 2026-07-31 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `134255` — event `487` — tier `exact`

- stored name: `Intuit Inc.`
- stored count **493**, date `2026-07-31`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Intuit Inc.` — 493 — 2026-07-31 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 40. Meta Platforms, Inc. (CA)

`warn-ca-2026-05-22-meta-platforms` — currently `not_matched`, stratum `large_census`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-05-22**, effective 2026-07-22..2026-07-22
- **3,270** affected across 6 published row(s)
  - Meta Platforms, Inc. — 81 — Alameda County; 6530 Paseo Padre Parkway  Fremont CA 94555 — `page 18, text row at y=94.2`
  - Meta Platforms, Inc. — 338 — San Mateo County; 311 Airport Boulevard  Burlingame CA 94010 — `page 18, text row at y=86.6`
  - Meta Platforms, Inc. — 252 — San Francisco County; 250 Howard St  San Francisco CA 94105 — `page 18, text row at y=79.1`
  - Meta Platforms, Inc. — 74 — Los Angeles County; 12105 E Waterfront Drive  Playa Vista CA 90094 — `page 18, text row at y=71.5`
  - Meta Platforms, Inc. — 2212 — San Mateo County; 1 Hacker Way  Menlo Park CA 94025 — `page 18, text row at y=64.0`
  - Meta Platforms, Inc. — 313 — Santa Clara County; 1180 Discovery Way  Sunnyvale CA 94089 — `page 18, text row at y=56.4`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2026-04-22 .. 2027-06-26

**8 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135027` — event `950` — tier `exact`

- stored name: `Meta Platforms, Inc.`
- stored count **74**, date `2026-05-29`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Meta Platforms, Inc.` — 74 — 2026-05-29 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is 7 day(s) after the notice date

### row `134372` — event `560` — tier `exact`

- stored name: `Meta Platforms, Inc.`
- stored count **313**, date `2026-07-22`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Meta Platforms, Inc.` — 313 — 2026-07-22 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `134371` — event `559` — tier `exact`

- stored name: `Meta Platforms, Inc.`
- stored count **2212**, date `2026-07-22`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Meta Platforms, Inc.` — 2212 — 2026-07-22 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `134370` — event `558` — tier `exact`

- stored name: `Meta Platforms, Inc.`
- stored count **74**, date `2026-07-22`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Meta Platforms, Inc.` — 74 — 2026-07-22 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `134369` — event `557` — tier `exact`

- stored name: `Meta Platforms, Inc.`
- stored count **252**, date `2026-07-22`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Meta Platforms, Inc.` — 252 — 2026-07-22 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `134368` — event `556` — tier `exact`

- stored name: `Meta Platforms, Inc.`
- stored count **338**, date `2026-07-22`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Meta Platforms, Inc.` — 338 — 2026-07-22 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `134367` — event `555` — tier `exact`

- stored name: `Meta Platforms, Inc.`
- stored count **81**, date `2026-07-22`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Meta Platforms, Inc.` — 81 — 2026-07-22 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `135085` — event `985` — tier `loose`

- stored name: `Meta Platforms, Inc.`
- stored count **124**, date `2026-05-22`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Meta Platforms, Inc.` — 124 — 2026-05-22 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 124 matches neither a component row nor the notice total 3270
  - row date is 0 day(s) after the notice date

---

## 41. KBR Services LLC (CA)

`warn-ca-2026-05-24-kbr-services` — currently `not_matched`, stratum `large_census`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-05-24**, effective 2026-08-01..2026-08-01
- **650** affected across 1 published row(s)
  - KBR Services LLC — 650 — San Bernardino County; National Training Center, Bldg. 896, Langford Lake Road  Barstow CA 92311 — `page 18, text row at y=48.8`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2026-04-24 .. 2027-06-28

**2 candidate row(s).** Each block below is one row and says nothing about any other.

### row `134247` — event `483` — tier `exact`

- stored name: `KBR Services LLC`
- stored count **650**, date `2026-08-01`, state `CA`, source `warn` / `CA WARN notice`
- live now: `KBR Services LLC` — 650 — 2026-08-01 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `135210` — event `1064` — tier `loose`

- stored name: `KBR Services LLC`
- stored count **758**, date `2026-05-06`, state `CA`, source `warn` / `CA WARN notice`
- live now: `KBR Services LLC` — 758 — 2026-05-06 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count 758 matches neither a component row nor the notice total 650
  - row date is -18 day(s) after the notice date

---

## 42. Tricor Industrial, Inc DBA Astrolite Alloys (CA)

`warn-ca-2026-05-29-tricor-industrial-dba-astrolite` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-05-29**, effective 2026-07-31..2026-07-31
- **6** affected across 1 published row(s)
  - Tricor Industrial, Inc DBA Astrolite Alloys — 6 — Ventura County; 201 Bernoulli Circle  Oxnard CA 93030 — `page 19, text row at y=517.6`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2026-04-29 .. 2027-07-03

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `134264` — event `496` — tier `exact`

- stored name: `Tricor Industrial, Inc DBA Astrolite Alloys`
- stored count **6**, date `2026-07-31`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Tricor Industrial, Inc DBA Astrolite Alloys` — 6 — 2026-07-31 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 43. Vine Hospitality (LB Steak Bishop Ranch, LP) (CA)

`warn-ca-2026-06-21-vine-hospitality` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-06-21**, effective 2026-06-23..2026-06-23
- **365** affected across 8 published row(s)
  - Vine Hospitality (LB Steak Bishop Ranch, LP) — 51 — Contra Costa County; 6000 Bollinger Canyon Road, Suite 1614  San Ramon CA 94583 — `page 20, text row at y=464.6`
  - Vine Hospitality (Left Bank Tiburon, LP) — 20 — Marin County; 1696 Tiburon Blvd  Tiburon CA 94920 — `page 20, text row at y=457.1`
  - Vine Hospitality (Blue Rock Restaurant Partners, LP) — 54 — Marin County; 507 Magnolia Avenue  Larkspur CA 94939 — `page 20, text row at y=449.5`
  - Vine Hospitality (Left Bank Menlo Park Partners, LP) — 42 — San Mateo County; 635 Santa Cruz Avenue  Menlo Park CA 94025 — `page 20, text row at y=442.0`
  - Vine Hospitality (Meso Santana Row, LP) — 54 — Santa Clara County; 3060 Olsen Drive, Suite 50  San Jose CA 95128 — `page 20, text row at y=434.4`
  - Vine Hospitality (La Rive Gauche San Jose, LLC) — 73 — Santa Clara County; 377 Santana Row, Suite 1100  San Jose CA 95128 — `page 20, text row at y=426.8`
  - Vine Hospitality (Santana Grill Partners, LP) — 59 — Santa Clara County; 344 Santana Row, Suite 1000  San Jose CA 95128 — `page 20, text row at y=419.3`
  - Vine Hospitality (Vine Dining Enterprises, Inc) — 12 — Santa Clara County; 3031 Tisch Way, Suite 90  San Jose CA 95128 — `page 20, text row at y=411.7`
- source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>
- the rule's match window: 2026-05-22 .. 2027-07-26

**8 candidate row(s).** Each block below is one row and says nothing about any other.

### row `134718` — event `767` — tier `exact`

- stored name: `Vine Hospitality (LB Steak Bishop Ranch, LP)`
- stored count **51**, date `2026-06-23`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Vine Hospitality (LB Steak Bishop Ranch, LP)` — 51 — 2026-06-23 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `134725` — event `774` — tier `exact`

- stored name: `Vine Hospitality (Vine Dining Enterprises, Inc)`
- stored count **12**, date `2026-06-23`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Vine Hospitality (Vine Dining Enterprises, Inc)` — 12 — 2026-06-23 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Vine Hospitality (Vine Dining Enterprises, Inc)' differs from the published 'Vine Hospitality (LB Steak Bishop Ranch, LP)'

### row `134724` — event `773` — tier `exact`

- stored name: `Vine Hospitality (Santana Grill Partners, LP)`
- stored count **59**, date `2026-06-23`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Vine Hospitality (Santana Grill Partners, LP)` — 59 — 2026-06-23 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Vine Hospitality (Santana Grill Partners, LP)' differs from the published 'Vine Hospitality (LB Steak Bishop Ranch, LP)'

### row `134723` — event `772` — tier `exact`

- stored name: `Vine Hospitality (La Rive Gauche San Jose, LLC)`
- stored count **73**, date `2026-06-23`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Vine Hospitality (La Rive Gauche San Jose, LLC)` — 73 — 2026-06-23 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Vine Hospitality (La Rive Gauche San Jose, LLC)' differs from the published 'Vine Hospitality (LB Steak Bishop Ranch, LP)'

### row `134722` — event `771` — tier `exact`

- stored name: `Vine Hospitality (Meso Santana Row, LP)`
- stored count **54**, date `2026-06-23`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Vine Hospitality (Meso Santana Row, LP)` — 54 — 2026-06-23 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Vine Hospitality (Meso Santana Row, LP)' differs from the published 'Vine Hospitality (LB Steak Bishop Ranch, LP)'

### row `134721` — event `770` — tier `exact`

- stored name: `Vine Hospitality (Left Bank Menlo Park Partners, LP)`
- stored count **42**, date `2026-06-23`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Vine Hospitality (Left Bank Menlo Park Partners, LP)` — 42 — 2026-06-23 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Vine Hospitality (Left Bank Menlo Park Partners, LP)' differs from the published 'Vine Hospitality (LB Steak Bishop Ranch, LP)'

### row `134720` — event `769` — tier `exact`

- stored name: `Vine Hospitality (Blue Rock Restaurant Partners, LP)`
- stored count **54**, date `2026-06-23`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Vine Hospitality (Blue Rock Restaurant Partners, LP)` — 54 — 2026-06-23 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Vine Hospitality (Blue Rock Restaurant Partners, LP)' differs from the published 'Vine Hospitality (LB Steak Bishop Ranch, LP)'

### row `134719` — event `768` — tier `exact`

- stored name: `Vine Hospitality (Left Bank Tiburon, LP)`
- stored count **20**, date `2026-06-23`, state `CA`, source `warn` / `CA WARN notice`
- live now: `Vine Hospitality (Left Bank Tiburon, LP)` — 20 — 2026-06-23 — `warn`
- our cited source: <https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Vine Hospitality (Left Bank Tiburon, LP)' differs from the published 'Vine Hospitality (LB Steak Bishop Ranch, LP)'

---

## 44. BlueCross BlueShield of Tennessee, Inc. (TN)

`warn-tn-2025-07-02-bluecross-blueshield-of-tennessee` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-07-02**, effective 2025-09-01..2025-09-01
- **150** affected across 1 published row(s)
  - BlueCross BlueShield of Tennessee, Inc. — 150 — Hamilton — `report table row 69`
- source: <https://www.tn.gov/content/dam/tn/workforce/archive/documents/majorpublications/reports-02/BlueCross-BlueShield-TDLWD-WARN-Letter.pdf>
- the rule's match window: 2025-06-02 .. 2026-08-06

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `137751` — event `2471` — tier `exact`

- stored name: `BlueCross BlueShield of Tennessee, Inc.`
- stored count **150**, date `2025-09-01`, state `TN`, source `warn` / `TN WARN notice`
- live now: `BlueCross BlueShield of Tennessee, Inc.` — 150 — 2025-09-01 — `warn`
- our cited source: <https://www.tn.gov/workforce/general-resources/major-publications0/major-publications-redirect/reports.html>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 45. GEODIS Logistics, LLC (TN)

`warn-tn-2025-07-24-geodis-logistics` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-07-24**, effective 2025-09-30..2025-09-30
- **57** affected across 1 published row(s)
  - GEODIS Logistics, LLC — 57 — Wilson — `report table row 67`
- source: <https://www.tn.gov/content/dam/tn/workforce/archive/documents/majorpublications/reports-02/GEODIS-Logistics-TDLWD-WARN-Letter.pdf>
- the rule's match window: 2025-06-24 .. 2026-08-28

**2 candidate row(s).** Each block below is one row and says nothing about any other.

### row `137485` — event `2320` — tier `exact`

- stored name: `GEODIS Logistics, LLC`
- stored count **57**, date `2025-09-30`, state `TN`, source `warn` / `TN WARN notice`
- live now: `GEODIS Logistics, LLC` — 57 — 2025-09-30 — `warn`
- our cited source: <https://www.tn.gov/workforce/general-resources/major-publications0/major-publications-redirect/reports.html>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `138049` — event `2608` — tier `loose`

- stored name: `GEODIS Logistics, LLC`
- stored count **40**, date `2025-07-31`, state `TN`, source `warn` / `TN WARN notice`
- live now: `GEODIS Logistics, LLC` — 40 — 2025-07-31 — `warn`
- our cited source: <https://www.tn.gov/workforce/general-resources/major-publications0/major-publications-redirect/reports.html>
- flags for this row:
  - job_count 40 matches neither a component row nor the notice total 57
  - row date is 7 day(s) after the notice date

---

## 46. FedEx Supply Chain (TN)

`warn-tn-2025-08-27-fedex-supply-chain` — currently `not_matched`, stratum `primary`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-08-27**, effective 2025-10-11..2025-10-11
- **611** affected across 1 published row(s)
  - FedEx Supply Chain — 611 — Shelby — `report table row 65`
- source: <https://www.tn.gov/content/dam/tn/workforce/archive/documents/majorpublications/reports-02/FedEx-Supply-Chain-TDLWD-WARN-Letter.pdf>
- the rule's match window: 2025-07-28 .. 2026-10-01

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `137315` — event `2211` — tier `exact`

- stored name: `FedEx Supply Chain`
- stored count **611**, date `2025-10-11`, state `TN`, source `warn` / `TN WARN notice`
- live now: `FedEx Supply Chain` — 611 — 2025-10-11 — `warn`
- our cited source: <https://www.tn.gov/workforce/general-resources/major-publications0/major-publications-redirect/reports.html>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 47. DoubleTree by Memphis (TN)

`warn-tn-2025-09-30-doubletree-by-memphis` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-09-30**, effective 2025-11-30..2025-11-30
- **88** affected across 1 published row(s)
  - DoubleTree by Memphis — 88 — Shelby — `report table row 63`
- source: <https://www.tn.gov/content/dam/tn/workforce/archive/documents/majorpublications/reports-02/DoubleTree-by-Hilton-Memphis-TDLWD-WARN-Letter.pdf>
- the rule's match window: 2025-08-31 .. 2026-11-04

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136884` — event `1970` — tier `exact`

- stored name: `DoubleTree by Memphis`
- stored count **88**, date `2025-11-30`, state `TN`, source `warn` / `TN WARN notice`
- live now: `DoubleTree by Memphis` — 88 — 2025-11-30 — `warn`
- our cited source: <https://www.tn.gov/workforce/general-resources/major-publications0/major-publications-redirect/reports.html>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 48. OP Mobility (TN)

`warn-tn-2025-10-07-op-mobility` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-10-07**, effective 2025-11-21..2025-11-21
- **82** affected across 1 published row(s)
  - OP Mobility — 82 — Maury — `report table row 61`
- source: <https://www.tn.gov/content/dam/tn/workforce/archive/documents/majorpublications/reports/OPMobilityTDLWDWARNLETTER.pdf>
- the rule's match window: 2025-09-07 .. 2026-11-11

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136950` — event `2009` — tier `exact`

- stored name: `OP Mobility`
- stored count **82**, date `2025-11-21`, state `TN`, source `warn` / `TN WARN notice`
- live now: `OP Mobility` — 82 — 2025-11-21 — `warn`
- our cited source: <https://www.tn.gov/workforce/general-resources/major-publications0/major-publications-redirect/reports.html>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 49. Crescent Park Corporation (TN)

`warn-tn-2025-10-17-crescent-park` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-10-17**, effective 2025-12-19..2025-12-19
- **76** affected across 1 published row(s)
  - Crescent Park Corporation — 76 — Shelby — `report table row 59`
- source: <https://www.tn.gov/content/dam/tn/workforce/archive/documents/majorpublications/reports-02/Crescent-Park-Corporation-TDLWD-WARN-Letter.pdf>
- the rule's match window: 2025-09-17 .. 2026-11-21

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136715` — event `1883` — tier `exact`

- stored name: `Crescent Park Corporation`
- stored count **76**, date `2025-12-19`, state `TN`, source `warn` / `TN WARN notice`
- live now: `Crescent Park Corporation` — 76 — 2025-12-19 — `warn`
- our cited source: <https://www.tn.gov/workforce/general-resources/major-publications0/major-publications-redirect/reports.html>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 50. HD Supply (TN)

`warn-tn-2025-10-27-hd-supply` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-10-27**, effective 2026-01-09..2026-01-09
- **108** affected across 1 published row(s)
  - HD Supply — 108 — Rutherford — `report table row 57`
- source: <https://www.tn.gov/content/dam/tn/workforce/archive/documents/majorpublications/reports-02/HD-Supply-TDLWD-WARN-Letter.pdf>
- the rule's match window: 2025-09-27 .. 2026-12-01

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136439` — event `1695` — tier `exact`

- stored name: `HD Supply`
- stored count **108**, date `2026-01-09`, state `TN`, source `warn` / `TN WARN notice`
- live now: `HD Supply` — 108 — 2026-01-09 — `warn`
- our cited source: <https://www.tn.gov/workforce/general-resources/major-publications0/major-publications-redirect/reports.html>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 51. GM - Ultium Cells Facility (TN)

`warn-tn-2025-10-30-gm` — currently `not_matched`, stratum `primary`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-10-30**, effective 2026-01-05..2026-01-05
- **710** affected across 1 published row(s)
  - GM - Ultium Cells Facility — 710 — Maury — `report table row 54`
- source: <https://www.tn.gov/content/dam/tn/workforce/archive/documents/majorpublications/reports-02/GM-Ultium-Cells-Facility-TDLWD-WARN-Letter.pdf>
- the rule's match window: 2025-09-30 .. 2026-12-04

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136470` — event `1712` — tier `exact`

- stored name: `GM - Ultium Cells Facility`
- stored count **710**, date `2026-01-05`, state `TN`, source `warn` / `TN WARN notice`
- live now: `GM - Ultium Cells Facility` — 710 — 2026-01-05 — `warn`
- our cited source: <https://www.tn.gov/workforce/general-resources/major-publications0/major-publications-redirect/reports.html>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 52. Creative Dining Services, Inc. (TN)

`warn-tn-2025-11-07-creative-dining-services` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-11-07**, effective 2025-12-13..2025-12-13
- **100** affected across 1 published row(s)
  - Creative Dining Services, Inc. — 100 — Chester — `report table row 53`
- source: <https://www.tn.gov/content/dam/tn/workforce/archive/documents/majorpublications/reports-02/Creative-Dining-Services-TDLWD-WARN-Letter.pdf>
- the rule's match window: 2025-10-08 .. 2026-12-12

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136769` — event `1916` — tier `exact`

- stored name: `Creative Dining Services, Inc.`
- stored count **100**, date `2025-12-13`, state `TN`, source `warn` / `TN WARN notice`
- live now: `Creative Dining Services, Inc.` — 100 — 2025-12-13 — `warn`
- our cited source: <https://www.tn.gov/workforce/general-resources/major-publications0/major-publications-redirect/reports.html>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 53. Edgewell Personal Care (TN)

`warn-tn-2025-11-14-edgewell-personal-care` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-11-14**, effective 2026-06-01..2026-06-01
- **132** affected across 1 published row(s)
  - Edgewell Personal Care — 132 — Knox — `report table row 51`
- source: <https://www.tn.gov/content/dam/tn/workforce/archive/documents/warn/Edgewell-Personal-Care-WARN-Letter.pdf>
- the rule's match window: 2025-10-15 .. 2026-12-19

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `134968` — event `916` — tier `exact`

- stored name: `Edgewell Personal Care`
- stored count **132**, date `2026-06-01`, state `TN`, source `warn` / `TN WARN notice`
- live now: `Edgewell Personal Care` — 132 — 2026-06-01 — `warn`
- our cited source: <https://www.tn.gov/workforce/general-resources/major-publications0/major-publications-redirect/reports.html>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 54. Kroger Fulfillment Network LLC (TN)

`warn-tn-2025-12-03-kroger-fulfillment-network` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-12-03**, effective 2026-02-01..2026-02-01
- **132** affected across 1 published row(s)
  - Kroger Fulfillment Network LLC — 132 — Davidson — `report table row 49`
- source: <https://www.tn.gov/content/dam/tn/workforce/archive/documents/warn/Kroger-Fulfillment-Network-WARN-Letter.pdf>
- the rule's match window: 2025-11-03 .. 2027-01-07

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136213` — event `1574` — tier `exact`

- stored name: `Kroger Fulfillment Network LLC`
- stored count **132**, date `2026-02-01`, state `TN`, source `warn` / `TN WARN notice`
- live now: `Kroger Fulfillment Network LLC` — 132 — 2026-02-01 — `warn`
- our cited source: <https://www.tn.gov/workforce/general-resources/major-publications0/major-publications-redirect/reports.html>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 55. Archer Daniels Midland Company (TN)

`warn-tn-2025-12-19-archer-daniels-midland` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-12-19**, effective 2026-01-30..2026-01-30
- **95** affected across 1 published row(s)
  - Archer Daniels Midland Company — 95 — Shelby — `report table row 47`
- source: <https://www.tn.gov/content/dam/tn/workforce/archive/documents/warn/Archer-Daniels-Midland-TDLWD-WARN-Letter.pdf>
- the rule's match window: 2025-11-19 .. 2027-01-23

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136254` — event `1585` — tier `exact`

- stored name: `Archer Daniels Midland Company`
- stored count **95**, date `2026-01-30`, state `TN`, source `warn` / `TN WARN notice`
- live now: `Archer Daniels Midland Company` — 95 — 2026-01-30 — `warn`
- our cited source: <https://www.tn.gov/workforce/general-resources/major-publications0/major-publications-redirect/reports.html>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 56. Linamar Shelbyville (TN)

`warn-tn-2026-01-13-linamar-shelbyville` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-01-13**, effective None..None
- **80** affected across 1 published row(s)
  - Linamar Shelbyville — 80 — Bedford — `report table row 44`
- source: <https://www.tn.gov/content/dam/tn/workforce/documents/warn/Linamar-Shelbyville.pdf>
- the rule's match window: 2025-12-14 .. 2027-02-17

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136415` — event `42247` — tier `exact`

- stored name: `Linamar Shelbyville`
- stored count **80**, date `2026-01-13`, state `TN`, source `warn` / `TN WARN notice`
- live now: `Linamar Shelbyville` — 80 — 2026-01-13 — `warn`
- our cited source: <https://www.tn.gov/workforce/general-resources/major-publications0/major-publications-redirect/reports.html>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is 0 day(s) after the notice date

---

## 57. Smoky Mountain Logistics, LLC (TN)

`warn-tn-2026-01-26-smoky-mountain-logistics` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-01-26**, effective 2026-03-24..2026-03-24
- **100** affected across 1 published row(s)
  - Smoky Mountain Logistics, LLC — 100 — Wilson — `report table row 43`
- source: <https://www.tn.gov/content/dam/tn/workforce/documents/warn/Smoky-Mountain-Logistics-LLC.pdf>
- the rule's match window: 2025-12-27 .. 2027-03-02

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136338` — event `42238` — tier `exact`

- stored name: `Smoky Mountain Logistics, LLC`
- stored count **100**, date `2026-01-26`, state `TN`, source `warn` / `TN WARN notice`
- live now: `Smoky Mountain Logistics, LLC` — 100 — 2026-01-26 — `warn`
- our cited source: <https://www.tn.gov/workforce/general-resources/major-publications0/major-publications-redirect/reports.html>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is 0 day(s) after the notice date

---

## 58. NIKE Retail Services, Inc. (TN)

`warn-tn-2026-01-27-nike-retail-services` — currently `not_matched`, stratum `large_census`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-01-27**, effective 2026-04-03..2026-04-03
- **583** affected across 1 published row(s)
  - NIKE Retail Services, Inc. — 583 — Shelby — `report table row 41`
- source: <https://www.tn.gov/content/dam/tn/workforce/documents/warn/NIKE-Retail-Services.pdf>
- the rule's match window: 2025-12-28 .. 2027-03-03

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136293` — event `42236` — tier `exact`

- stored name: `NIKE Retail Services, Inc.`
- stored count **583**, date `2026-01-27`, state `TN`, source `warn` / `TN WARN notice`
- live now: `NIKE Retail Services, Inc.` — 583 — 2026-01-27 — `warn`
- our cited source: <https://www.tn.gov/workforce/general-resources/major-publications0/major-publications-redirect/reports.html>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is 0 day(s) after the notice date

---

## 59. DLH Solutions (TN)

`warn-tn-2026-01-30-dlh-solutions` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-01-30**, effective 2026-03-31..2026-03-31
- **209** affected across 1 published row(s)
  - DLH Solutions — 209 — Rutherford — `report table row 39`
- source: <https://www.tn.gov/content/dam/tn/workforce/documents/warn/DLH-Solutions.pdf>
- the rule's match window: 2025-12-31 .. 2027-03-06

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135751` — event `1365` — tier `exact`

- stored name: `DLH Solutions`
- stored count **209**, date `2026-03-31`, state `TN`, source `warn` / `TN WARN notice`
- live now: `DLH Solutions` — 209 — 2026-03-31 — `warn`
- our cited source: <https://www.tn.gov/workforce/general-resources/major-publications0/major-publications-redirect/reports.html>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 60. Premiere Building Maintenance Corporation (TN)

`warn-tn-2026-02-03-premiere-building-maintenance` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-02-03**, effective 2026-03-31..2026-03-31
- **154** affected across 1 published row(s)
  - Premiere Building Maintenance Corporation — 154 — Knox — `report table row 38`
- source: <https://www.tn.gov/content/dam/tn/workforce/documents/warn/Premiere-Building-Maintenance.pdf>
- the rule's match window: 2026-01-04 .. 2027-03-10

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135752` — event `1366` — tier `exact`

- stored name: `Premiere Building Maintenance Corporation`
- stored count **154**, date `2026-03-31`, state `TN`, source `warn` / `TN WARN notice`
- live now: `Premiere Building Maintenance Corporation` — 154 — 2026-03-31 — `warn`
- our cited source: <https://www.tn.gov/workforce/general-resources/major-publications0/major-publications-redirect/reports.html>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 61. Liberty Dental Plan (TN)

`warn-tn-2026-02-19-liberty-dental-plan` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-02-19**, effective 2026-04-06..2026-04-06
- **1** affected across 1 published row(s)
  - Liberty Dental Plan — 1 — Bradley — `report table row 37`
- source: <https://www.tn.gov/content/dam/tn/workforce/documents/warn/Liberty-Dental-Plan.pdf>
- the rule's match window: 2026-01-20 .. 2027-03-26

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135635` — event `1294` — tier `exact`

- stored name: `Liberty Dental Plan`
- stored count **1**, date `2026-04-06`, state `TN`, source `warn` / `TN WARN notice`
- live now: `Liberty Dental Plan` — 1 — 2026-04-06 — `warn`
- our cited source: <https://www.tn.gov/workforce/general-resources/major-publications0/major-publications-redirect/reports.html>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 62. McKay Books, Inc. (TN)

`warn-tn-2026-03-02-mckay-books` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-03-02**, effective 2026-05-03..2026-05-03
- **54** affected across 1 published row(s)
  - McKay Books, Inc. — 54 — Knox — `report table row 34`
- source: <https://www.tn.gov/content/dam/tn/workforce/documents/warn/McKay-Books.pdf>
- the rule's match window: 2026-01-31 .. 2027-04-06

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136015` — event `42216` — tier `exact`

- stored name: `McKay Books, Inc.`
- stored count **54**, date `2026-03-02`, state `TN`, source `warn` / `TN WARN notice`
- live now: `McKay Books, Inc.` — 54 — 2026-03-02 — `warn`
- our cited source: <https://www.tn.gov/workforce/general-resources/major-publications0/major-publications-redirect/reports.html>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is 0 day(s) after the notice date

---

## 63. First Brands Group, LLC (TN)

`warn-tn-2026-03-04-first-brands` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-03-04**, effective 2026-04-30..2026-04-30
- **333** affected across 1 published row(s)
  - First Brands Group, LLC — 333 — Lincoln — `report table row 32`
- source: <https://www.tn.gov/content/dam/tn/workforce/documents/warn/First-Brands-Group.pdf>
- the rule's match window: 2026-02-02 .. 2027-04-08

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136003` — event `42214` — tier `exact`

- stored name: `First Brands Group, LLC`
- stored count **333**, date `2026-03-04`, state `TN`, source `warn` / `TN WARN notice`
- live now: `First Brands Group, LLC` — 333 — 2026-03-04 — `warn`
- our cited source: <https://www.tn.gov/workforce/general-resources/major-publications0/major-publications-redirect/reports.html>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is 0 day(s) after the notice date

---

## 64. IKEA Memphis (TN)

`warn-tn-2026-03-05-ikea-memphis` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-03-05**, effective None..None
- **114** affected across 1 published row(s)
  - IKEA Memphis — 114 — Shelby — `report table row 31`
- source: <https://www.tn.gov/content/dam/tn/workforce/documents/warn/IKEA-Memphis.pdf>
- the rule's match window: 2026-02-03 .. 2027-04-09

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135997` — event `42212` — tier `exact`

- stored name: `IKEA Memphis`
- stored count **114**, date `2026-03-05`, state `TN`, source `warn` / `TN WARN notice`
- live now: `IKEA Memphis` — 114 — 2026-03-05 — `warn`
- our cited source: <https://www.tn.gov/workforce/general-resources/major-publications0/major-publications-redirect/reports.html>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is 0 day(s) after the notice date

---

## 65. Blount Memorial Hospital (TN)

`warn-tn-2026-03-24-blount-memorial-hospital` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-03-24**, effective 2026-05-01..2026-05-01
- **85** affected across 1 published row(s)
  - Blount Memorial Hospital — 85 — Blount — `report table row 28`
- source: <https://www.tn.gov/content/dam/tn/workforce/documents/warn/Blount-Memorial-Hospital.pdf>
- the rule's match window: 2026-02-22 .. 2027-04-28

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135814` — event `42188` — tier `exact`

- stored name: `Blount Memorial Hospital`
- stored count **85**, date `2026-03-24`, state `TN`, source `warn` / `TN WARN notice`
- live now: `Blount Memorial Hospital` — 85 — 2026-03-24 — `warn`
- our cited source: <https://www.tn.gov/workforce/general-resources/major-publications0/major-publications-redirect/reports.html>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is 0 day(s) after the notice date

---

## 66. Durham School Services (TN)

`warn-tn-2026-04-10-durham-school-services` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-04-10**, effective 2026-06-06..2026-06-06
- **79** affected across 1 published row(s)
  - Durham School Services — 79 — Warren — `report table row 26`
- source: <https://www.tn.gov/content/dam/tn/workforce/documents/warn/Durham-School-Services.pdf>
- the rule's match window: 2026-03-11 .. 2027-05-15

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135592` — event `42175` — tier `exact`

- stored name: `Durham School Services`
- stored count **79**, date `2026-04-10`, state `TN`, source `warn` / `TN WARN notice`
- live now: `Durham School Services` — 79 — 2026-04-10 — `warn`
- our cited source: <https://www.tn.gov/workforce/general-resources/major-publications0/major-publications-redirect/reports.html>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is 0 day(s) after the notice date

---

## 67. Pave It Forward Logistics (TN)

`warn-tn-2026-04-15-pave-it-forward-logistics` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-04-15**, effective 2026-03-31..2026-03-31
- **100** affected across 1 published row(s)
  - Pave It Forward Logistics — 100 — Rutherford — `report table row 24`
- source: <https://www.tn.gov/content/dam/tn/workforce/documents/warn/Pave-It-Forward-Logistics.pdf>
- the rule's match window: 2026-03-16 .. 2027-05-20

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135536` — event `42170` — tier `exact`

- stored name: `Pave It Forward Logistics`
- stored count **100**, date `2026-04-15`, state `TN`, source `warn` / `TN WARN notice`
- live now: `Pave It Forward Logistics` — 100 — 2026-04-15 — `warn`
- our cited source: <https://www.tn.gov/workforce/general-resources/major-publications0/major-publications-redirect/reports.html>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is 0 day(s) after the notice date

---

## 68. Adient (TN)

`warn-tn-2026-04-21-adient` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-04-21**, effective 2026-06-30..2026-06-30
- **210** affected across 1 published row(s)
  - Adient — 210 — McMinn — `report table row 22`
- source: <https://www.tn.gov/content/dam/tn/workforce/documents/warn/Adient.pdf>
- the rule's match window: 2026-03-22 .. 2027-05-26

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135470` — event `42159` — tier `exact`

- stored name: `Adient`
- stored count **210**, date `2026-04-21`, state `TN`, source `warn` / `TN WARN notice`
- live now: `Adient` — 210 — 2026-04-21 — `warn`
- our cited source: <https://www.tn.gov/workforce/general-resources/major-publications0/major-publications-redirect/reports.html>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is 0 day(s) after the notice date

---

## 69. Fayette County Public Schools (TN)

`warn-tn-2026-05-04-fayette-county-public-schools` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-05-04**, effective 2026-06-30..2026-06-30
- **75** affected across 1 published row(s)
  - Fayette County Public Schools — 75 — Fayette — `report table row 20`
- source: <https://www.tn.gov/content/dam/tn/workforce/documents/warn/Fayette-County-Public-Schools.pdf>
- the rule's match window: 2026-04-04 .. 2027-06-08

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135237` — event `42133` — tier `exact`

- stored name: `Fayette County Public Schools`
- stored count **75**, date `2026-05-04`, state `TN`, source `warn` / `TN WARN notice`
- live now: `Fayette County Public Schools` — 75 — 2026-05-04 — `warn`
- our cited source: <https://www.tn.gov/workforce/general-resources/major-publications0/major-publications-redirect/reports.html>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is 0 day(s) after the notice date

---

## 70. International Business Machines-Coppell (TX)

`warn-tx-2025-07-02-international-business-machines-coppell` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-07-02**, effective 2025-08-29..2025-08-29
- **59** affected across 1 published row(s)
  - International Business Machines-Coppell — 59 — Coppell, Dallas — `$order=notice_date, $offset=0 within the window filter`
- source: <https://data.texas.gov/resource/8w53-c4f6.json>
- the rule's match window: 2025-06-02 .. 2026-08-06

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `137811` — event `110646` — tier `exact`

- stored name: `International Business Machines-Coppell`
- stored count **59**, date `2025-08-29`, state `TX`, source `warn` / `TX WARN notice`
- live now: `International Business Machines-Coppell` — 59 — 2025-08-29 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 71. Intel Corporation (TX)

`warn-tx-2025-07-09-intel` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-07-09**, effective 2025-07-15..2025-07-15
- **110** affected across 1 published row(s)
  - Intel Corporation — 110 — Austin, Travis — `$order=notice_date, $offset=8 within the window filter`
- source: <https://data.texas.gov/resource/8w53-c4f6.json>
- the rule's match window: 2025-06-09 .. 2026-08-13

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `138170` — event `111005` — tier `exact`

- stored name: `Intel Corporation`
- stored count **110**, date `2025-07-15`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Intel Corporation` — 110 — 2025-07-15 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 72. SM Cargo (TX)

`warn-tx-2025-07-21-sm-cargo` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-07-21**, effective 2025-09-21..2025-09-21
- **194** affected across 1 published row(s)
  - SM Cargo — 194 — Houston, Harris — `$order=notice_date, $offset=20 within the window filter`
- source: <https://data.texas.gov/resource/8w53-c4f6.json>
- the rule's match window: 2025-06-21 .. 2026-08-25

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `137593` — event `110428` — tier `exact`

- stored name: `SM Cargo`
- stored count **194**, date `2025-09-21`, state `TX`, source `warn` / `TX WARN notice`
- live now: `SM Cargo` — 194 — 2025-09-21 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 73. Chevron Corporation (HESS Corporation) (TX)

`warn-tx-2025-07-21-chevron` — currently `not_matched`, stratum `large_census`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-07-21**, effective 2025-09-26..2025-09-26
- **575** affected across 1 published row(s)
  - Chevron Corporation (HESS Corporation) — 575 — Houston, Harris — `$order=notice_date, $offset=21 within the window filter`
- source: <https://data.texas.gov/resource/8w53-c4f6.json>
- the rule's match window: 2025-06-21 .. 2026-08-25

**4 candidate row(s).** Each block below is one row and says nothing about any other.

### row `137555` — event `110390` — tier `exact`

- stored name: `Chevron Corporation (HESS Corporation)`
- stored count **575**, date `2025-09-26`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Chevron Corporation (HESS Corporation)` — 575 — 2025-09-26 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `138173` — event `111008` — tier `loose`

- stored name: `Chevron (Deauville Blvd)`
- stored count **185**, date `2025-07-15`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Chevron (Deauville Blvd)` — 185 — 2025-07-15 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 185 matches neither a component row nor the notice total 575
  - row date is -6 day(s) after the notice date
  - stored name 'Chevron (Deauville Blvd)' differs from the published 'Chevron Corporation (HESS Corporation)'

### row `138172` — event `111007` — tier `loose`

- stored name: `Chevron (S. County Rd.)`
- stored count **1**, date `2025-07-15`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Chevron (S. County Rd.)` — 1 — 2025-07-15 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 1 matches neither a component row nor the notice total 575
  - row date is -6 day(s) after the notice date
  - stored name 'Chevron (S. County Rd.)' differs from the published 'Chevron Corporation (HESS Corporation)'

### row `138171` — event `111006` — tier `loose`

- stored name: `Chevron (N. FM 1788)`
- stored count **14**, date `2025-07-15`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Chevron (N. FM 1788)` — 14 — 2025-07-15 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 14 matches neither a component row nor the notice total 575
  - row date is -6 day(s) after the notice date
  - stored name 'Chevron (N. FM 1788)' differs from the published 'Chevron Corporation (HESS Corporation)'

---

## 74. Equus Workforce Solutions Stephenville (Arbor E&T, LLC) (TX)

`warn-tx-2025-07-30-equus-workforce-solutions-stephenville` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-07-30**, effective 2025-09-30..2025-09-30
- **2** affected across 1 published row(s)
  - Equus Workforce Solutions Stephenville (Arbor E&T, LLC) — 2 — Stephenville, Erath — `$order=notice_date, $offset=28 within the window filter`
- source: <https://data.texas.gov/resource/8w53-c4f6.json>
- the rule's match window: 2025-06-30 .. 2026-09-03

**18 candidate row(s).** Each block below is one row and says nothing about any other.

### row `137507` — event `110342` — tier `exact`

- stored name: `Equus Workforce Solutions Stephenville (Arbor E&T, LLC)`
- stored count **2**, date `2025-09-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Equus Workforce Solutions Stephenville (Arbor E&T, LLC)` — 2 — 2025-09-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `137511` — event `110346` — tier `loose`

- stored name: `Equus Workforce Solutions Arlington (Arbor E&T, LLC)`
- stored count **4**, date `2025-09-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Equus Workforce Solutions Arlington (Arbor E&T, LLC)` — 4 — 2025-09-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 4 matches neither a component row nor the notice total 2
  - row date equals this notice's earliest published effective date
  - stored name 'Equus Workforce Solutions Arlington (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions Stephenville (Arbor E&T, LLC)'

### row `137510` — event `110345` — tier `loose`

- stored name: `Equus Workforce Solutions Denton (Arbor E&T, LLC)`
- stored count **27**, date `2025-09-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Equus Workforce Solutions Denton (Arbor E&T, LLC)` — 27 — 2025-09-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 27 matches neither a component row nor the notice total 2
  - row date equals this notice's earliest published effective date
  - stored name 'Equus Workforce Solutions Denton (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions Stephenville (Arbor E&T, LLC)'

### row `137509` — event `110344` — tier `loose`

- stored name: `Equus Workforce Solutions Greenville (Arbor E&T, LLC)`
- stored count **9**, date `2025-09-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Equus Workforce Solutions Greenville (Arbor E&T, LLC)` — 9 — 2025-09-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 9 matches neither a component row nor the notice total 2
  - row date equals this notice's earliest published effective date
  - stored name 'Equus Workforce Solutions Greenville (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions Stephenville (Arbor E&T, LLC)'

### row `137508` — event `110343` — tier `loose`

- stored name: `Equus Workforce Solutions McKinney (Arbor E&T, LLC)`
- stored count **15**, date `2025-09-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Equus Workforce Solutions McKinney (Arbor E&T, LLC)` — 15 — 2025-09-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 15 matches neither a component row nor the notice total 2
  - row date equals this notice's earliest published effective date
  - stored name 'Equus Workforce Solutions McKinney (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions Stephenville (Arbor E&T, LLC)'

### row `137506` — event `110341` — tier `loose`

- stored name: `Equus Workforce Solutions Terrell (Arbor E&T, LLC)`
- stored count **8**, date `2025-09-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Equus Workforce Solutions Terrell (Arbor E&T, LLC)` — 8 — 2025-09-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 8 matches neither a component row nor the notice total 2
  - row date equals this notice's earliest published effective date
  - stored name 'Equus Workforce Solutions Terrell (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions Stephenville (Arbor E&T, LLC)'

### row `137505` — event `110340` — tier `loose`

- stored name: `Equus Workforce Solutions Weatherford (Arbor E&T, LLC)`
- stored count **16**, date `2025-09-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Equus Workforce Solutions Weatherford (Arbor E&T, LLC)` — 16 — 2025-09-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 16 matches neither a component row nor the notice total 2
  - row date equals this notice's earliest published effective date
  - stored name 'Equus Workforce Solutions Weatherford (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions Stephenville (Arbor E&T, LLC)'

### row `137504` — event `110339` — tier `loose`

- stored name: `Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC)`
- stored count **1**, date `2025-09-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC)` — 1 — 2025-09-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 1 matches neither a component row nor the notice total 2
  - row date equals this notice's earliest published effective date
  - stored name 'Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions Stephenville (Arbor E&T, LLC)'

### row `137503` — event `110338` — tier `loose`

- stored name: `Equus Workforce Solutions-N.Tenth St. (Arbor E&T, LLC)`
- stored count **10**, date `2025-09-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Equus Workforce Solutions-N.Tenth St. (Arbor E&T, LLC)` — 10 — 2025-09-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 10 matches neither a component row nor the notice total 2
  - row date equals this notice's earliest published effective date
  - stored name 'Equus Workforce Solutions-N.Tenth St. (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions Stephenville (Arbor E&T, LLC)'

### row `137502` — event `110337` — tier `loose`

- stored name: `Equus Workforce Solutions-Highway 161. (Arbor E&T, LLC)`
- stored count **71**, date `2025-09-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Equus Workforce Solutions-Highway 161. (Arbor E&T, LLC)` — 71 — 2025-09-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 71 matches neither a component row nor the notice total 2
  - row date equals this notice's earliest published effective date
  - stored name 'Equus Workforce Solutions-Highway 161. (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions Stephenville (Arbor E&T, LLC)'

### row `137501` — event `110336` — tier `loose`

- stored name: `Equus Workforce Solutions-Greenville Ave. (Arbor E&T, LLC)`
- stored count **10**, date `2025-09-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Equus Workforce Solutions-Greenville Ave. (Arbor E&T, LLC)` — 10 — 2025-09-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 10 matches neither a component row nor the notice total 2
  - row date equals this notice's earliest published effective date
  - stored name 'Equus Workforce Solutions-Greenville Ave. (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions Stephenville (Arbor E&T, LLC)'

### row `137500` — event `110335` — tier `loose`

- stored name: `Equus Workforce Solutions-Irving Blvd. (Arbor E&T, LLC)`
- stored count **13**, date `2025-09-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Equus Workforce Solutions-Irving Blvd. (Arbor E&T, LLC)` — 13 — 2025-09-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 13 matches neither a component row nor the notice total 2
  - row date equals this notice's earliest published effective date
  - stored name 'Equus Workforce Solutions-Irving Blvd. (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions Stephenville (Arbor E&T, LLC)'

### row `137499` — event `110334` — tier `loose`

- stored name: `Equus Workforce Solutions-Alpha Rd.(Arbor E&T, LLC)`
- stored count **17**, date `2025-09-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Equus Workforce Solutions-Alpha Rd.(Arbor E&T, LLC)` — 17 — 2025-09-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 17 matches neither a component row nor the notice total 2
  - row date equals this notice's earliest published effective date
  - stored name 'Equus Workforce Solutions-Alpha Rd.(Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions Stephenville (Arbor E&T, LLC)'

### row `137498` — event `110333` — tier `loose`

- stored name: `Equus Workforce Solutions-Malcolm X Blvd.(Arbor E&T, LLC)`
- stored count **16**, date `2025-09-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Equus Workforce Solutions-Malcolm X Blvd.(Arbor E&T, LLC)` — 16 — 2025-09-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 16 matches neither a component row nor the notice total 2
  - row date equals this notice's earliest published effective date
  - stored name 'Equus Workforce Solutions-Malcolm X Blvd.(Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions Stephenville (Arbor E&T, LLC)'

### row `137497` — event `110332` — tier `loose`

- stored name: `Equus Workforce Solutions-Buckner Blvd.(Arbor E&T, LLC)`
- stored count **16**, date `2025-09-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Equus Workforce Solutions-Buckner Blvd.(Arbor E&T, LLC)` — 16 — 2025-09-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 16 matches neither a component row nor the notice total 2
  - row date equals this notice's earliest published effective date
  - stored name 'Equus Workforce Solutions-Buckner Blvd.(Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions Stephenville (Arbor E&T, LLC)'

### row `137494` — event `110329` — tier `loose`

- stored name: `Equus Workforce Solutions Houston Opertions- Acres Home (Arbor E&T, LLC)`
- stored count **12**, date `2025-09-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Equus Workforce Solutions Houston Opertions- Acres Home (Arbor E&T, LLC)` — 12 — 2025-09-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 12 matches neither a component row nor the notice total 2
  - row date equals this notice's earliest published effective date
  - stored name 'Equus Workforce Solutions Houston Opertions- Acres Home (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions Stephenville (Arbor E&T, LLC)'

### row `137493` — event `110328` — tier `loose`

- stored name: `Equus Workforce Solutions Houston Opertions- Pearland (Arbor E&T, LLC)`
- stored count **13**, date `2025-09-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Equus Workforce Solutions Houston Opertions- Pearland (Arbor E&T, LLC)` — 13 — 2025-09-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 13 matches neither a component row nor the notice total 2
  - row date equals this notice's earliest published effective date
  - stored name 'Equus Workforce Solutions Houston Opertions- Pearland (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions Stephenville (Arbor E&T, LLC)'

### row `137492` — event `110327` — tier `loose`

- stored name: `Equus Workforce Solutions Houston Opertions- Westheimer Rd. (Arbor E&T, LLC)`
- stored count **28**, date `2025-09-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Equus Workforce Solutions Houston Opertions- Westheimer Rd. (Arbor E&T, LLC)` — 28 — 2025-09-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 28 matches neither a component row nor the notice total 2
  - row date equals this notice's earliest published effective date
  - stored name 'Equus Workforce Solutions Houston Opertions- Westheimer Rd. (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions Stephenville (Arbor E&T, LLC)'

---

## 75. Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC) (TX)

`warn-tx-2025-07-31-equus-workforce-solutions-camp` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-07-31**, effective 2025-09-30..2025-09-30
- **1** affected across 1 published row(s)
  - Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC) — 1 — Dallas, Dallas — `$order=notice_date, $offset=31 within the window filter`
- source: <https://data.texas.gov/resource/8w53-c4f6.json>
- the rule's match window: 2025-07-01 .. 2026-09-04

**18 candidate row(s).** Each block below is one row and says nothing about any other.

### row `137504` — event `110339` — tier `exact`

- stored name: `Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC)`
- stored count **1**, date `2025-09-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC)` — 1 — 2025-09-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `137511` — event `110346` — tier `loose`

- stored name: `Equus Workforce Solutions Arlington (Arbor E&T, LLC)`
- stored count **4**, date `2025-09-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Equus Workforce Solutions Arlington (Arbor E&T, LLC)` — 4 — 2025-09-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 4 matches neither a component row nor the notice total 1
  - row date equals this notice's earliest published effective date
  - stored name 'Equus Workforce Solutions Arlington (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC)'

### row `137510` — event `110345` — tier `loose`

- stored name: `Equus Workforce Solutions Denton (Arbor E&T, LLC)`
- stored count **27**, date `2025-09-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Equus Workforce Solutions Denton (Arbor E&T, LLC)` — 27 — 2025-09-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 27 matches neither a component row nor the notice total 1
  - row date equals this notice's earliest published effective date
  - stored name 'Equus Workforce Solutions Denton (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC)'

### row `137509` — event `110344` — tier `loose`

- stored name: `Equus Workforce Solutions Greenville (Arbor E&T, LLC)`
- stored count **9**, date `2025-09-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Equus Workforce Solutions Greenville (Arbor E&T, LLC)` — 9 — 2025-09-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 9 matches neither a component row nor the notice total 1
  - row date equals this notice's earliest published effective date
  - stored name 'Equus Workforce Solutions Greenville (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC)'

### row `137508` — event `110343` — tier `loose`

- stored name: `Equus Workforce Solutions McKinney (Arbor E&T, LLC)`
- stored count **15**, date `2025-09-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Equus Workforce Solutions McKinney (Arbor E&T, LLC)` — 15 — 2025-09-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 15 matches neither a component row nor the notice total 1
  - row date equals this notice's earliest published effective date
  - stored name 'Equus Workforce Solutions McKinney (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC)'

### row `137507` — event `110342` — tier `loose`

- stored name: `Equus Workforce Solutions Stephenville (Arbor E&T, LLC)`
- stored count **2**, date `2025-09-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Equus Workforce Solutions Stephenville (Arbor E&T, LLC)` — 2 — 2025-09-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 2 matches neither a component row nor the notice total 1
  - row date equals this notice's earliest published effective date
  - stored name 'Equus Workforce Solutions Stephenville (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC)'

### row `137506` — event `110341` — tier `loose`

- stored name: `Equus Workforce Solutions Terrell (Arbor E&T, LLC)`
- stored count **8**, date `2025-09-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Equus Workforce Solutions Terrell (Arbor E&T, LLC)` — 8 — 2025-09-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 8 matches neither a component row nor the notice total 1
  - row date equals this notice's earliest published effective date
  - stored name 'Equus Workforce Solutions Terrell (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC)'

### row `137505` — event `110340` — tier `loose`

- stored name: `Equus Workforce Solutions Weatherford (Arbor E&T, LLC)`
- stored count **16**, date `2025-09-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Equus Workforce Solutions Weatherford (Arbor E&T, LLC)` — 16 — 2025-09-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 16 matches neither a component row nor the notice total 1
  - row date equals this notice's earliest published effective date
  - stored name 'Equus Workforce Solutions Weatherford (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC)'

### row `137503` — event `110338` — tier `loose`

- stored name: `Equus Workforce Solutions-N.Tenth St. (Arbor E&T, LLC)`
- stored count **10**, date `2025-09-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Equus Workforce Solutions-N.Tenth St. (Arbor E&T, LLC)` — 10 — 2025-09-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 10 matches neither a component row nor the notice total 1
  - row date equals this notice's earliest published effective date
  - stored name 'Equus Workforce Solutions-N.Tenth St. (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC)'

### row `137502` — event `110337` — tier `loose`

- stored name: `Equus Workforce Solutions-Highway 161. (Arbor E&T, LLC)`
- stored count **71**, date `2025-09-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Equus Workforce Solutions-Highway 161. (Arbor E&T, LLC)` — 71 — 2025-09-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 71 matches neither a component row nor the notice total 1
  - row date equals this notice's earliest published effective date
  - stored name 'Equus Workforce Solutions-Highway 161. (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC)'

### row `137501` — event `110336` — tier `loose`

- stored name: `Equus Workforce Solutions-Greenville Ave. (Arbor E&T, LLC)`
- stored count **10**, date `2025-09-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Equus Workforce Solutions-Greenville Ave. (Arbor E&T, LLC)` — 10 — 2025-09-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 10 matches neither a component row nor the notice total 1
  - row date equals this notice's earliest published effective date
  - stored name 'Equus Workforce Solutions-Greenville Ave. (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC)'

### row `137500` — event `110335` — tier `loose`

- stored name: `Equus Workforce Solutions-Irving Blvd. (Arbor E&T, LLC)`
- stored count **13**, date `2025-09-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Equus Workforce Solutions-Irving Blvd. (Arbor E&T, LLC)` — 13 — 2025-09-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 13 matches neither a component row nor the notice total 1
  - row date equals this notice's earliest published effective date
  - stored name 'Equus Workforce Solutions-Irving Blvd. (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC)'

### row `137499` — event `110334` — tier `loose`

- stored name: `Equus Workforce Solutions-Alpha Rd.(Arbor E&T, LLC)`
- stored count **17**, date `2025-09-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Equus Workforce Solutions-Alpha Rd.(Arbor E&T, LLC)` — 17 — 2025-09-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 17 matches neither a component row nor the notice total 1
  - row date equals this notice's earliest published effective date
  - stored name 'Equus Workforce Solutions-Alpha Rd.(Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC)'

### row `137498` — event `110333` — tier `loose`

- stored name: `Equus Workforce Solutions-Malcolm X Blvd.(Arbor E&T, LLC)`
- stored count **16**, date `2025-09-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Equus Workforce Solutions-Malcolm X Blvd.(Arbor E&T, LLC)` — 16 — 2025-09-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 16 matches neither a component row nor the notice total 1
  - row date equals this notice's earliest published effective date
  - stored name 'Equus Workforce Solutions-Malcolm X Blvd.(Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC)'

### row `137497` — event `110332` — tier `loose`

- stored name: `Equus Workforce Solutions-Buckner Blvd.(Arbor E&T, LLC)`
- stored count **16**, date `2025-09-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Equus Workforce Solutions-Buckner Blvd.(Arbor E&T, LLC)` — 16 — 2025-09-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 16 matches neither a component row nor the notice total 1
  - row date equals this notice's earliest published effective date
  - stored name 'Equus Workforce Solutions-Buckner Blvd.(Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC)'

### row `137494` — event `110329` — tier `loose`

- stored name: `Equus Workforce Solutions Houston Opertions- Acres Home (Arbor E&T, LLC)`
- stored count **12**, date `2025-09-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Equus Workforce Solutions Houston Opertions- Acres Home (Arbor E&T, LLC)` — 12 — 2025-09-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 12 matches neither a component row nor the notice total 1
  - row date equals this notice's earliest published effective date
  - stored name 'Equus Workforce Solutions Houston Opertions- Acres Home (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC)'

### row `137493` — event `110328` — tier `loose`

- stored name: `Equus Workforce Solutions Houston Opertions- Pearland (Arbor E&T, LLC)`
- stored count **13**, date `2025-09-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Equus Workforce Solutions Houston Opertions- Pearland (Arbor E&T, LLC)` — 13 — 2025-09-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 13 matches neither a component row nor the notice total 1
  - row date equals this notice's earliest published effective date
  - stored name 'Equus Workforce Solutions Houston Opertions- Pearland (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC)'

### row `137492` — event `110327` — tier `loose`

- stored name: `Equus Workforce Solutions Houston Opertions- Westheimer Rd. (Arbor E&T, LLC)`
- stored count **28**, date `2025-09-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Equus Workforce Solutions Houston Opertions- Westheimer Rd. (Arbor E&T, LLC)` — 28 — 2025-09-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 28 matches neither a component row nor the notice total 1
  - row date equals this notice's earliest published effective date
  - stored name 'Equus Workforce Solutions Houston Opertions- Westheimer Rd. (Arbor E&T, LLC)' differs from the published 'Equus Workforce Solutions-Camp Wisdom (Arbor E&T, LLC)'

---

## 76. Planned Parenthood Gulf Coast (Prevention Park Facility) (TX)

`warn-tx-2025-07-31-planned-parenthood-gulf-coast` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-07-31**, effective 2025-09-30..2025-09-30
- **114** affected across 1 published row(s)
  - Planned Parenthood Gulf Coast (Prevention Park Facility) — 114 — Houston, Harris — `$order=notice_date, $offset=40 within the window filter`
- source: <https://data.texas.gov/resource/8w53-c4f6.json>
- the rule's match window: 2025-07-01 .. 2026-09-04

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `137495` — event `110330` — tier `exact`

- stored name: `Planned Parenthood Gulf Coast (Prevention Park Facility)`
- stored count **114**, date `2025-09-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Planned Parenthood Gulf Coast (Prevention Park Facility)` — 114 — 2025-09-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 77. Southwest Key Programs, Inc. (Casa Houston Reliant) (TX)

`warn-tx-2025-07-31-southwest-key-programs` — currently `not_matched`, stratum `large_census`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-07-31**, effective 2025-10-05..2025-10-05
- **1,213** affected across 7 published row(s)
  - Southwest Key Programs, Inc. (Casa Houston Reliant) — 211 — Houston, Harris — `$order=notice_date, $offset=41 within the window filter`
  - Southwest Key Programs, Inc. (Houston HQ) — 11 — Houston, Harris — `$order=notice_date, $offset=42 within the window filter`
  - Southwest Key Programs, Inc. (Casa Quetzal) — 309 — Houston, Harris — `$order=notice_date, $offset=43 within the window filter`
  - Southwest Key Programs, Inc. (Casa Sunzal) — 223 — Houston, Harris — `$order=notice_date, $offset=44 within the window filter`
  - Southwest Key Programs, Inc. (Casa Oasis) — 128 — McAllen, Hidalgo — `$order=notice_date, $offset=45 within the window filter`
  - Southwest Key Programs, Inc. (Casa Sueno) — 93 — Weslaco, Hidalgo — `$order=notice_date, $offset=46 within the window filter`
  - Southwest Key Programs, Inc. (Casa Montezuma) — 238 — Channelview, Harris — `$order=notice_date, $offset=47 within the window filter`
- source: <https://data.texas.gov/resource/8w53-c4f6.json>
- the rule's match window: 2025-07-01 .. 2026-09-04

**25 candidate row(s).** Each block below is one row and says nothing about any other.

### row `137377` — event `110212` — tier `exact`

- stored name: `Southwest Key Programs, Inc. (Casa Houston Reliant)`
- stored count **211**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc. (Casa Houston Reliant)` — 211 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `137376` — event `110211` — tier `exact`

- stored name: `Southwest Key Programs, Inc. (Houston HQ)`
- stored count **11**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc. (Houston HQ)` — 11 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Southwest Key Programs, Inc. (Houston HQ)' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)'

### row `137375` — event `110210` — tier `exact`

- stored name: `Southwest Key Programs, Inc. (Casa Quetzal)`
- stored count **309**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc. (Casa Quetzal)` — 309 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Southwest Key Programs, Inc. (Casa Quetzal)' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)'

### row `137374` — event `110209` — tier `exact`

- stored name: `Southwest Key Programs, Inc. (Casa Sunzal)`
- stored count **223**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc. (Casa Sunzal)` — 223 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Southwest Key Programs, Inc. (Casa Sunzal)' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)'

### row `137373` — event `110208` — tier `exact`

- stored name: `Southwest Key Programs, Inc. (Casa Oasis)`
- stored count **128**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc. (Casa Oasis)` — 128 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Southwest Key Programs, Inc. (Casa Oasis)' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)'

### row `137372` — event `110207` — tier `exact`

- stored name: `Southwest Key Programs, Inc. (Casa Sueno)`
- stored count **93**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc. (Casa Sueno)` — 93 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Southwest Key Programs, Inc. (Casa Sueno)' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)'

### row `137371` — event `110206` — tier `exact`

- stored name: `Southwest Key Programs, Inc. (Casa Montezuma)`
- stored count **238**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc. (Casa Montezuma)` — 238 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Southwest Key Programs, Inc. (Casa Montezuma)' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)'

### row `137370` — event `110205` — tier `loose`

- stored name: `Southwest Key Programs, Inc. La Esperanza)`
- stored count **4**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc. La Esperanza)` — 4 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 4 matches neither a component row nor the notice total 1213
  - row date equals this notice's earliest published effective date
  - stored name 'Southwest Key Programs, Inc. La Esperanza)' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)'

### row `137369` — event `110204` — tier `loose`

- stored name: `Southwest Key Programs, Inc.(Casa Nueva Esperanza)`
- stored count **9**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc.(Casa Nueva Esperanza)` — 9 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 9 matches neither a component row nor the notice total 1213
  - row date equals this notice's earliest published effective date
  - stored name 'Southwest Key Programs, Inc.(Casa Nueva Esperanza)' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)'

### row `137368` — event `110203` — tier `loose`

- stored name: `Southwest Key Programs, Inc.(South Texas HQ)`
- stored count **13**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc.(South Texas HQ)` — 13 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 13 matches neither a component row nor the notice total 1213
  - row date equals this notice's earliest published effective date
  - stored name 'Southwest Key Programs, Inc.(South Texas HQ)' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)'

### row `137367` — event `110202` — tier `loose`

- stored name: `Southwest Key Programs, Inc. (Casa Franklin)`
- stored count **1**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc. (Casa Franklin)` — 1 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 1 matches neither a component row nor the notice total 1213
  - row date equals this notice's earliest published effective date
  - stored name 'Southwest Key Programs, Inc. (Casa Franklin)' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)'

### row `137366` — event `110201` — tier `loose`

- stored name: `Southwest Key Programs, Inc. (Casa Norma Linda)`
- stored count **3**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc. (Casa Norma Linda)` — 3 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 3 matches neither a component row nor the notice total 1213
  - row date equals this notice's earliest published effective date
  - stored name 'Southwest Key Programs, Inc. (Casa Norma Linda)' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)'

### row `137365` — event `110200` — tier `loose`

- stored name: `Southwest Key Programs, Inc. (Casa Rio Grande)`
- stored count **3**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc. (Casa Rio Grande)` — 3 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 3 matches neither a component row nor the notice total 1213
  - row date equals this notice's earliest published effective date
  - stored name 'Southwest Key Programs, Inc. (Casa Rio Grande)' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)'

### row `137364` — event `110199` — tier `loose`

- stored name: `Southwest Key Programs, Inc. (Casa Canutillo)`
- stored count **3**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc. (Casa Canutillo)` — 3 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 3 matches neither a component row nor the notice total 1213
  - row date equals this notice's earliest published effective date
  - stored name 'Southwest Key Programs, Inc. (Casa Canutillo)' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)'

### row `137359` — event `110194` — tier `loose`

- stored name: `Southwest Key Programs, Inc. (SWK National Headquarters)`
- stored count **45**, date `2025-10-06`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc. (SWK National Headquarters)` — 45 — 2025-10-06 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 45 matches neither a component row nor the notice total 1213
  - row date is 67 day(s) after the notice date
  - stored name 'Southwest Key Programs, Inc. (SWK National Headquarters)' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)'

### row `137093` — event `109928` — tier `loose`

- stored name: `Southwest Key Programs-Casa Canutillo`
- stored count **2**, date `2025-11-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs-Casa Canutillo` — 2 — 2025-11-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 2 matches neither a component row nor the notice total 1213
  - row date is 97 day(s) after the notice date
  - stored name 'Southwest Key Programs-Casa Canutillo' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)'

### row `137092` — event `109927` — tier `loose`

- stored name: `Southwest Key Programs-Casita Del Valle`
- stored count **5**, date `2025-11-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs-Casita Del Valle` — 5 — 2025-11-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 5 matches neither a component row nor the notice total 1213
  - row date is 97 day(s) after the notice date
  - stored name 'Southwest Key Programs-Casita Del Valle' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)'

### row `137091` — event `109926` — tier `loose`

- stored name: `Southwest Key Programs-Casa Houston Reliant`
- stored count **1**, date `2025-11-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs-Casa Houston Reliant` — 1 — 2025-11-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 1 matches neither a component row nor the notice total 1213
  - row date is 97 day(s) after the notice date
  - stored name 'Southwest Key Programs-Casa Houston Reliant' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)'

### row `137090` — event `109925` — tier `loose`

- stored name: `Southwest Key Programs-Casa Montezuma`
- stored count **1**, date `2025-11-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs-Casa Montezuma` — 1 — 2025-11-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 1 matches neither a component row nor the notice total 1213
  - row date is 97 day(s) after the notice date
  - stored name 'Southwest Key Programs-Casa Montezuma' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)'

### row `137089` — event `109924` — tier `loose`

- stored name: `Southwest Key Programs-Casa Norma Linda`
- stored count **3**, date `2025-11-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs-Casa Norma Linda` — 3 — 2025-11-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 3 matches neither a component row nor the notice total 1213
  - row date is 97 day(s) after the notice date
  - stored name 'Southwest Key Programs-Casa Norma Linda' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)'

### row `137088` — event `109923` — tier `loose`

- stored name: `Southwest Key Programs-Casa Nueva Esperanza`
- stored count **8**, date `2025-11-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs-Casa Nueva Esperanza` — 8 — 2025-11-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 8 matches neither a component row nor the notice total 1213
  - row date is 97 day(s) after the notice date
  - stored name 'Southwest Key Programs-Casa Nueva Esperanza' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)'

### row `137087` — event `109922` — tier `loose`

- stored name: `Southwest Key Programs-Casa Rio Grande`
- stored count **3**, date `2025-11-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs-Casa Rio Grande` — 3 — 2025-11-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 3 matches neither a component row nor the notice total 1213
  - row date is 97 day(s) after the notice date
  - stored name 'Southwest Key Programs-Casa Rio Grande' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)'

### row `137086` — event `109921` — tier `loose`

- stored name: `Southwest Key Programs-National Headquarters (Austin)`
- stored count **3**, date `2025-11-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs-National Headquarters (Austin)` — 3 — 2025-11-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 3 matches neither a component row nor the notice total 1213
  - row date is 97 day(s) after the notice date
  - stored name 'Southwest Key Programs-National Headquarters (Austin)' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)'

### row `137085` — event `109920` — tier `loose`

- stored name: `Southwest Key Programs-STX Regional Headquarters`
- stored count **12**, date `2025-11-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs-STX Regional Headquarters` — 12 — 2025-11-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 12 matches neither a component row nor the notice total 1213
  - row date is 97 day(s) after the notice date
  - stored name 'Southwest Key Programs-STX Regional Headquarters' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)'

### row `137084` — event `109919` — tier `loose`

- stored name: `Southwest Key Programs-Houston Headquarters`
- stored count **10**, date `2025-11-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs-Houston Headquarters` — 10 — 2025-11-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 10 matches neither a component row nor the notice total 1213
  - row date is 97 day(s) after the notice date
  - stored name 'Southwest Key Programs-Houston Headquarters' differs from the published 'Southwest Key Programs, Inc. (Casa Houston Reliant)'

---

## 78. Southwest Key Programs, Inc. La Esperanza) (TX)

`warn-tx-2025-08-06-southwest-key-programs-la` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-08-06**, effective 2025-10-05..2025-10-05
- **4** affected across 1 published row(s)
  - Southwest Key Programs, Inc. La Esperanza) — 4 — Brownsville, Cameron — `$order=notice_date, $offset=54 within the window filter`
- source: <https://data.texas.gov/resource/8w53-c4f6.json>
- the rule's match window: 2025-07-07 .. 2026-09-10

**25 candidate row(s).** Each block below is one row and says nothing about any other.

### row `137370` — event `110205` — tier `exact`

- stored name: `Southwest Key Programs, Inc. La Esperanza)`
- stored count **4**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc. La Esperanza)` — 4 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `137377` — event `110212` — tier `loose`

- stored name: `Southwest Key Programs, Inc. (Casa Houston Reliant)`
- stored count **211**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc. (Casa Houston Reliant)` — 211 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 211 matches neither a component row nor the notice total 4
  - row date equals this notice's earliest published effective date
  - stored name 'Southwest Key Programs, Inc. (Casa Houston Reliant)' differs from the published 'Southwest Key Programs, Inc. La Esperanza)'

### row `137376` — event `110211` — tier `loose`

- stored name: `Southwest Key Programs, Inc. (Houston HQ)`
- stored count **11**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc. (Houston HQ)` — 11 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 11 matches neither a component row nor the notice total 4
  - row date equals this notice's earliest published effective date
  - stored name 'Southwest Key Programs, Inc. (Houston HQ)' differs from the published 'Southwest Key Programs, Inc. La Esperanza)'

### row `137375` — event `110210` — tier `loose`

- stored name: `Southwest Key Programs, Inc. (Casa Quetzal)`
- stored count **309**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc. (Casa Quetzal)` — 309 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 309 matches neither a component row nor the notice total 4
  - row date equals this notice's earliest published effective date
  - stored name 'Southwest Key Programs, Inc. (Casa Quetzal)' differs from the published 'Southwest Key Programs, Inc. La Esperanza)'

### row `137374` — event `110209` — tier `loose`

- stored name: `Southwest Key Programs, Inc. (Casa Sunzal)`
- stored count **223**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc. (Casa Sunzal)` — 223 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 223 matches neither a component row nor the notice total 4
  - row date equals this notice's earliest published effective date
  - stored name 'Southwest Key Programs, Inc. (Casa Sunzal)' differs from the published 'Southwest Key Programs, Inc. La Esperanza)'

### row `137373` — event `110208` — tier `loose`

- stored name: `Southwest Key Programs, Inc. (Casa Oasis)`
- stored count **128**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc. (Casa Oasis)` — 128 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 128 matches neither a component row nor the notice total 4
  - row date equals this notice's earliest published effective date
  - stored name 'Southwest Key Programs, Inc. (Casa Oasis)' differs from the published 'Southwest Key Programs, Inc. La Esperanza)'

### row `137372` — event `110207` — tier `loose`

- stored name: `Southwest Key Programs, Inc. (Casa Sueno)`
- stored count **93**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc. (Casa Sueno)` — 93 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 93 matches neither a component row nor the notice total 4
  - row date equals this notice's earliest published effective date
  - stored name 'Southwest Key Programs, Inc. (Casa Sueno)' differs from the published 'Southwest Key Programs, Inc. La Esperanza)'

### row `137371` — event `110206` — tier `loose`

- stored name: `Southwest Key Programs, Inc. (Casa Montezuma)`
- stored count **238**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc. (Casa Montezuma)` — 238 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 238 matches neither a component row nor the notice total 4
  - row date equals this notice's earliest published effective date
  - stored name 'Southwest Key Programs, Inc. (Casa Montezuma)' differs from the published 'Southwest Key Programs, Inc. La Esperanza)'

### row `137369` — event `110204` — tier `loose`

- stored name: `Southwest Key Programs, Inc.(Casa Nueva Esperanza)`
- stored count **9**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc.(Casa Nueva Esperanza)` — 9 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 9 matches neither a component row nor the notice total 4
  - row date equals this notice's earliest published effective date
  - stored name 'Southwest Key Programs, Inc.(Casa Nueva Esperanza)' differs from the published 'Southwest Key Programs, Inc. La Esperanza)'

### row `137368` — event `110203` — tier `loose`

- stored name: `Southwest Key Programs, Inc.(South Texas HQ)`
- stored count **13**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc.(South Texas HQ)` — 13 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 13 matches neither a component row nor the notice total 4
  - row date equals this notice's earliest published effective date
  - stored name 'Southwest Key Programs, Inc.(South Texas HQ)' differs from the published 'Southwest Key Programs, Inc. La Esperanza)'

### row `137367` — event `110202` — tier `loose`

- stored name: `Southwest Key Programs, Inc. (Casa Franklin)`
- stored count **1**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc. (Casa Franklin)` — 1 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 1 matches neither a component row nor the notice total 4
  - row date equals this notice's earliest published effective date
  - stored name 'Southwest Key Programs, Inc. (Casa Franklin)' differs from the published 'Southwest Key Programs, Inc. La Esperanza)'

### row `137366` — event `110201` — tier `loose`

- stored name: `Southwest Key Programs, Inc. (Casa Norma Linda)`
- stored count **3**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc. (Casa Norma Linda)` — 3 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 3 matches neither a component row nor the notice total 4
  - row date equals this notice's earliest published effective date
  - stored name 'Southwest Key Programs, Inc. (Casa Norma Linda)' differs from the published 'Southwest Key Programs, Inc. La Esperanza)'

### row `137365` — event `110200` — tier `loose`

- stored name: `Southwest Key Programs, Inc. (Casa Rio Grande)`
- stored count **3**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc. (Casa Rio Grande)` — 3 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 3 matches neither a component row nor the notice total 4
  - row date equals this notice's earliest published effective date
  - stored name 'Southwest Key Programs, Inc. (Casa Rio Grande)' differs from the published 'Southwest Key Programs, Inc. La Esperanza)'

### row `137364` — event `110199` — tier `loose`

- stored name: `Southwest Key Programs, Inc. (Casa Canutillo)`
- stored count **3**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc. (Casa Canutillo)` — 3 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 3 matches neither a component row nor the notice total 4
  - row date equals this notice's earliest published effective date
  - stored name 'Southwest Key Programs, Inc. (Casa Canutillo)' differs from the published 'Southwest Key Programs, Inc. La Esperanza)'

### row `137359` — event `110194` — tier `loose`

- stored name: `Southwest Key Programs, Inc. (SWK National Headquarters)`
- stored count **45**, date `2025-10-06`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc. (SWK National Headquarters)` — 45 — 2025-10-06 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 45 matches neither a component row nor the notice total 4
  - row date is 61 day(s) after the notice date
  - stored name 'Southwest Key Programs, Inc. (SWK National Headquarters)' differs from the published 'Southwest Key Programs, Inc. La Esperanza)'

### row `137093` — event `109928` — tier `loose`

- stored name: `Southwest Key Programs-Casa Canutillo`
- stored count **2**, date `2025-11-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs-Casa Canutillo` — 2 — 2025-11-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 2 matches neither a component row nor the notice total 4
  - row date is 91 day(s) after the notice date
  - stored name 'Southwest Key Programs-Casa Canutillo' differs from the published 'Southwest Key Programs, Inc. La Esperanza)'

### row `137092` — event `109927` — tier `loose`

- stored name: `Southwest Key Programs-Casita Del Valle`
- stored count **5**, date `2025-11-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs-Casita Del Valle` — 5 — 2025-11-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 5 matches neither a component row nor the notice total 4
  - row date is 91 day(s) after the notice date
  - stored name 'Southwest Key Programs-Casita Del Valle' differs from the published 'Southwest Key Programs, Inc. La Esperanza)'

### row `137091` — event `109926` — tier `loose`

- stored name: `Southwest Key Programs-Casa Houston Reliant`
- stored count **1**, date `2025-11-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs-Casa Houston Reliant` — 1 — 2025-11-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 1 matches neither a component row nor the notice total 4
  - row date is 91 day(s) after the notice date
  - stored name 'Southwest Key Programs-Casa Houston Reliant' differs from the published 'Southwest Key Programs, Inc. La Esperanza)'

### row `137090` — event `109925` — tier `loose`

- stored name: `Southwest Key Programs-Casa Montezuma`
- stored count **1**, date `2025-11-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs-Casa Montezuma` — 1 — 2025-11-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 1 matches neither a component row nor the notice total 4
  - row date is 91 day(s) after the notice date
  - stored name 'Southwest Key Programs-Casa Montezuma' differs from the published 'Southwest Key Programs, Inc. La Esperanza)'

### row `137089` — event `109924` — tier `loose`

- stored name: `Southwest Key Programs-Casa Norma Linda`
- stored count **3**, date `2025-11-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs-Casa Norma Linda` — 3 — 2025-11-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 3 matches neither a component row nor the notice total 4
  - row date is 91 day(s) after the notice date
  - stored name 'Southwest Key Programs-Casa Norma Linda' differs from the published 'Southwest Key Programs, Inc. La Esperanza)'

### row `137088` — event `109923` — tier `loose`

- stored name: `Southwest Key Programs-Casa Nueva Esperanza`
- stored count **8**, date `2025-11-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs-Casa Nueva Esperanza` — 8 — 2025-11-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 8 matches neither a component row nor the notice total 4
  - row date is 91 day(s) after the notice date
  - stored name 'Southwest Key Programs-Casa Nueva Esperanza' differs from the published 'Southwest Key Programs, Inc. La Esperanza)'

### row `137087` — event `109922` — tier `loose`

- stored name: `Southwest Key Programs-Casa Rio Grande`
- stored count **3**, date `2025-11-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs-Casa Rio Grande` — 3 — 2025-11-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 3 matches neither a component row nor the notice total 4
  - row date is 91 day(s) after the notice date
  - stored name 'Southwest Key Programs-Casa Rio Grande' differs from the published 'Southwest Key Programs, Inc. La Esperanza)'

### row `137086` — event `109921` — tier `loose`

- stored name: `Southwest Key Programs-National Headquarters (Austin)`
- stored count **3**, date `2025-11-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs-National Headquarters (Austin)` — 3 — 2025-11-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 3 matches neither a component row nor the notice total 4
  - row date is 91 day(s) after the notice date
  - stored name 'Southwest Key Programs-National Headquarters (Austin)' differs from the published 'Southwest Key Programs, Inc. La Esperanza)'

### row `137085` — event `109920` — tier `loose`

- stored name: `Southwest Key Programs-STX Regional Headquarters`
- stored count **12**, date `2025-11-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs-STX Regional Headquarters` — 12 — 2025-11-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 12 matches neither a component row nor the notice total 4
  - row date is 91 day(s) after the notice date
  - stored name 'Southwest Key Programs-STX Regional Headquarters' differs from the published 'Southwest Key Programs, Inc. La Esperanza)'

### row `137084` — event `109919` — tier `loose`

- stored name: `Southwest Key Programs-Houston Headquarters`
- stored count **10**, date `2025-11-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs-Houston Headquarters` — 10 — 2025-11-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 10 matches neither a component row nor the notice total 4
  - row date is 91 day(s) after the notice date
  - stored name 'Southwest Key Programs-Houston Headquarters' differs from the published 'Southwest Key Programs, Inc. La Esperanza)'

---

## 79. Condair Operations, LLC (TX)

`warn-tx-2025-09-03-condair-operations` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-09-03**, effective 2025-11-03..2025-11-03
- **51** affected across 1 published row(s)
  - Condair Operations, LLC — 51 — Center, Shelby — `$order=notice_date, $offset=65 within the window filter`
- source: <https://data.texas.gov/resource/8w53-c4f6.json>
- the rule's match window: 2025-08-04 .. 2026-10-08

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `137117` — event `109952` — tier `exact`

- stored name: `Condair Operations, LLC`
- stored count **51**, date `2025-11-03`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Condair Operations, LLC` — 51 — 2025-11-03 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 80. Cottonwood Creek Healthcare Community (TX)

`warn-tx-2025-09-24-cottonwood-creek-healthcare-community` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-09-24**, effective 2025-12-01..2025-12-01
- **70** affected across 1 published row(s)
  - Cottonwood Creek Healthcare Community — 70 — Richardson, Dallas — `$order=notice_date, $offset=72 within the window filter`
- source: <https://data.texas.gov/resource/8w53-c4f6.json>
- the rule's match window: 2025-08-25 .. 2026-10-29

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136854` — event `109689` — tier `exact`

- stored name: `Cottonwood Creek Healthcare Community`
- stored count **70**, date `2025-12-01`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Cottonwood Creek Healthcare Community` — 70 — 2025-12-01 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 81. Holiday Inn Club Vacations Incorporated-The Villages Resort (TX)

`warn-tx-2025-09-30-holiday-inn-club-vacations` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-09-30**, effective 2025-11-28..2025-11-28
- **82** affected across 1 published row(s)
  - Holiday Inn Club Vacations Incorporated-The Villages Resort — 82 — Flint, Smith — `$order=notice_date, $offset=80 within the window filter`
- source: <https://data.texas.gov/resource/8w53-c4f6.json>
- the rule's match window: 2025-08-31 .. 2026-11-04

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136909` — event `109744` — tier `exact`

- stored name: `Holiday Inn Club Vacations Incorporated-The Villages Resort`
- stored count **82**, date `2025-11-28`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Holiday Inn Club Vacations Incorporated-The Villages Resort` — 82 — 2025-11-28 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 82. Southwest Key Programs-Casa Canutillo (TX)

`warn-tx-2025-10-02-southwest-key-programs-casa` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-10-02**, effective 2025-11-05..2025-11-05
- **18** affected across 6 published row(s)
  - Southwest Key Programs-Casa Canutillo — 2 — Canutillo, El Paso — `$order=notice_date, $offset=85 within the window filter`
  - Southwest Key Programs-Casa Houston Reliant — 1 — Houston, Harris — `$order=notice_date, $offset=87 within the window filter`
  - Southwest Key Programs-Casa Montezuma — 1 — Channelview, Harris — `$order=notice_date, $offset=88 within the window filter`
  - Southwest Key Programs-Casa Norma Linda — 3 — Los Fresnos, Cameron — `$order=notice_date, $offset=89 within the window filter`
  - Southwest Key Programs-Casa Nueva Esperanza — 8 — Brownsville, Cameron — `$order=notice_date, $offset=90 within the window filter`
  - Southwest Key Programs-Casa Rio Grande — 3 — San Benito, Cameron — `$order=notice_date, $offset=91 within the window filter`
- source: <https://data.texas.gov/resource/8w53-c4f6.json>
- the rule's match window: 2025-09-02 .. 2026-11-06

**25 candidate row(s).** Each block below is one row and says nothing about any other.

### row `137093` — event `109928` — tier `exact`

- stored name: `Southwest Key Programs-Casa Canutillo`
- stored count **2**, date `2025-11-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs-Casa Canutillo` — 2 — 2025-11-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `137367` — event `110202` — tier `exact`

- stored name: `Southwest Key Programs, Inc. (Casa Franklin)`
- stored count **1**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc. (Casa Franklin)` — 1 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is 3 day(s) after the notice date
  - stored name 'Southwest Key Programs, Inc. (Casa Franklin)' differs from the published 'Southwest Key Programs-Casa Canutillo'

### row `137366` — event `110201` — tier `exact`

- stored name: `Southwest Key Programs, Inc. (Casa Norma Linda)`
- stored count **3**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc. (Casa Norma Linda)` — 3 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is 3 day(s) after the notice date
  - stored name 'Southwest Key Programs, Inc. (Casa Norma Linda)' differs from the published 'Southwest Key Programs-Casa Canutillo'

### row `137365` — event `110200` — tier `exact`

- stored name: `Southwest Key Programs, Inc. (Casa Rio Grande)`
- stored count **3**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc. (Casa Rio Grande)` — 3 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is 3 day(s) after the notice date
  - stored name 'Southwest Key Programs, Inc. (Casa Rio Grande)' differs from the published 'Southwest Key Programs-Casa Canutillo'

### row `137364` — event `110199` — tier `exact`

- stored name: `Southwest Key Programs, Inc. (Casa Canutillo)`
- stored count **3**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc. (Casa Canutillo)` — 3 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is 3 day(s) after the notice date
  - stored name 'Southwest Key Programs, Inc. (Casa Canutillo)' differs from the published 'Southwest Key Programs-Casa Canutillo'

### row `137091` — event `109926` — tier `exact`

- stored name: `Southwest Key Programs-Casa Houston Reliant`
- stored count **1**, date `2025-11-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs-Casa Houston Reliant` — 1 — 2025-11-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Southwest Key Programs-Casa Houston Reliant' differs from the published 'Southwest Key Programs-Casa Canutillo'

### row `137090` — event `109925` — tier `exact`

- stored name: `Southwest Key Programs-Casa Montezuma`
- stored count **1**, date `2025-11-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs-Casa Montezuma` — 1 — 2025-11-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Southwest Key Programs-Casa Montezuma' differs from the published 'Southwest Key Programs-Casa Canutillo'

### row `137089` — event `109924` — tier `exact`

- stored name: `Southwest Key Programs-Casa Norma Linda`
- stored count **3**, date `2025-11-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs-Casa Norma Linda` — 3 — 2025-11-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Southwest Key Programs-Casa Norma Linda' differs from the published 'Southwest Key Programs-Casa Canutillo'

### row `137088` — event `109923` — tier `exact`

- stored name: `Southwest Key Programs-Casa Nueva Esperanza`
- stored count **8**, date `2025-11-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs-Casa Nueva Esperanza` — 8 — 2025-11-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Southwest Key Programs-Casa Nueva Esperanza' differs from the published 'Southwest Key Programs-Casa Canutillo'

### row `137087` — event `109922` — tier `exact`

- stored name: `Southwest Key Programs-Casa Rio Grande`
- stored count **3**, date `2025-11-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs-Casa Rio Grande` — 3 — 2025-11-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Southwest Key Programs-Casa Rio Grande' differs from the published 'Southwest Key Programs-Casa Canutillo'

### row `137086` — event `109921` — tier `exact`

- stored name: `Southwest Key Programs-National Headquarters (Austin)`
- stored count **3**, date `2025-11-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs-National Headquarters (Austin)` — 3 — 2025-11-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Southwest Key Programs-National Headquarters (Austin)' differs from the published 'Southwest Key Programs-Casa Canutillo'

### row `137377` — event `110212` — tier `loose`

- stored name: `Southwest Key Programs, Inc. (Casa Houston Reliant)`
- stored count **211**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc. (Casa Houston Reliant)` — 211 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 211 matches neither a component row nor the notice total 18
  - row date is 3 day(s) after the notice date
  - stored name 'Southwest Key Programs, Inc. (Casa Houston Reliant)' differs from the published 'Southwest Key Programs-Casa Canutillo'

### row `137376` — event `110211` — tier `loose`

- stored name: `Southwest Key Programs, Inc. (Houston HQ)`
- stored count **11**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc. (Houston HQ)` — 11 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 11 matches neither a component row nor the notice total 18
  - row date is 3 day(s) after the notice date
  - stored name 'Southwest Key Programs, Inc. (Houston HQ)' differs from the published 'Southwest Key Programs-Casa Canutillo'

### row `137375` — event `110210` — tier `loose`

- stored name: `Southwest Key Programs, Inc. (Casa Quetzal)`
- stored count **309**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc. (Casa Quetzal)` — 309 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 309 matches neither a component row nor the notice total 18
  - row date is 3 day(s) after the notice date
  - stored name 'Southwest Key Programs, Inc. (Casa Quetzal)' differs from the published 'Southwest Key Programs-Casa Canutillo'

### row `137374` — event `110209` — tier `loose`

- stored name: `Southwest Key Programs, Inc. (Casa Sunzal)`
- stored count **223**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc. (Casa Sunzal)` — 223 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 223 matches neither a component row nor the notice total 18
  - row date is 3 day(s) after the notice date
  - stored name 'Southwest Key Programs, Inc. (Casa Sunzal)' differs from the published 'Southwest Key Programs-Casa Canutillo'

### row `137373` — event `110208` — tier `loose`

- stored name: `Southwest Key Programs, Inc. (Casa Oasis)`
- stored count **128**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc. (Casa Oasis)` — 128 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 128 matches neither a component row nor the notice total 18
  - row date is 3 day(s) after the notice date
  - stored name 'Southwest Key Programs, Inc. (Casa Oasis)' differs from the published 'Southwest Key Programs-Casa Canutillo'

### row `137372` — event `110207` — tier `loose`

- stored name: `Southwest Key Programs, Inc. (Casa Sueno)`
- stored count **93**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc. (Casa Sueno)` — 93 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 93 matches neither a component row nor the notice total 18
  - row date is 3 day(s) after the notice date
  - stored name 'Southwest Key Programs, Inc. (Casa Sueno)' differs from the published 'Southwest Key Programs-Casa Canutillo'

### row `137371` — event `110206` — tier `loose`

- stored name: `Southwest Key Programs, Inc. (Casa Montezuma)`
- stored count **238**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc. (Casa Montezuma)` — 238 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 238 matches neither a component row nor the notice total 18
  - row date is 3 day(s) after the notice date
  - stored name 'Southwest Key Programs, Inc. (Casa Montezuma)' differs from the published 'Southwest Key Programs-Casa Canutillo'

### row `137370` — event `110205` — tier `loose`

- stored name: `Southwest Key Programs, Inc. La Esperanza)`
- stored count **4**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc. La Esperanza)` — 4 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 4 matches neither a component row nor the notice total 18
  - row date is 3 day(s) after the notice date
  - stored name 'Southwest Key Programs, Inc. La Esperanza)' differs from the published 'Southwest Key Programs-Casa Canutillo'

### row `137369` — event `110204` — tier `loose`

- stored name: `Southwest Key Programs, Inc.(Casa Nueva Esperanza)`
- stored count **9**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc.(Casa Nueva Esperanza)` — 9 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 9 matches neither a component row nor the notice total 18
  - row date is 3 day(s) after the notice date
  - stored name 'Southwest Key Programs, Inc.(Casa Nueva Esperanza)' differs from the published 'Southwest Key Programs-Casa Canutillo'

### row `137368` — event `110203` — tier `loose`

- stored name: `Southwest Key Programs, Inc.(South Texas HQ)`
- stored count **13**, date `2025-10-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc.(South Texas HQ)` — 13 — 2025-10-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 13 matches neither a component row nor the notice total 18
  - row date is 3 day(s) after the notice date
  - stored name 'Southwest Key Programs, Inc.(South Texas HQ)' differs from the published 'Southwest Key Programs-Casa Canutillo'

### row `137359` — event `110194` — tier `loose`

- stored name: `Southwest Key Programs, Inc. (SWK National Headquarters)`
- stored count **45**, date `2025-10-06`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs, Inc. (SWK National Headquarters)` — 45 — 2025-10-06 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 45 matches neither a component row nor the notice total 18
  - row date is 4 day(s) after the notice date
  - stored name 'Southwest Key Programs, Inc. (SWK National Headquarters)' differs from the published 'Southwest Key Programs-Casa Canutillo'

### row `137092` — event `109927` — tier `loose`

- stored name: `Southwest Key Programs-Casita Del Valle`
- stored count **5**, date `2025-11-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs-Casita Del Valle` — 5 — 2025-11-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 5 matches neither a component row nor the notice total 18
  - row date equals this notice's earliest published effective date
  - stored name 'Southwest Key Programs-Casita Del Valle' differs from the published 'Southwest Key Programs-Casa Canutillo'

### row `137085` — event `109920` — tier `loose`

- stored name: `Southwest Key Programs-STX Regional Headquarters`
- stored count **12**, date `2025-11-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs-STX Regional Headquarters` — 12 — 2025-11-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 12 matches neither a component row nor the notice total 18
  - row date equals this notice's earliest published effective date
  - stored name 'Southwest Key Programs-STX Regional Headquarters' differs from the published 'Southwest Key Programs-Casa Canutillo'

### row `137084` — event `109919` — tier `loose`

- stored name: `Southwest Key Programs-Houston Headquarters`
- stored count **10**, date `2025-11-05`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Southwest Key Programs-Houston Headquarters` — 10 — 2025-11-05 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 10 matches neither a component row nor the notice total 18
  - row date equals this notice's earliest published effective date
  - stored name 'Southwest Key Programs-Houston Headquarters' differs from the published 'Southwest Key Programs-Casa Canutillo'

---

## 83. Meadow Burke, LLC d/b/a Leviat (TX)

`warn-tx-2025-10-08-meadow-burke-d-b` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-10-08**, effective 2025-12-02..2025-12-02
- **75** affected across 1 published row(s)
  - Meadow Burke, LLC d/b/a Leviat — 75 — Fort Worth, Tarrant — `$order=notice_date, $offset=95 within the window filter`
- source: <https://data.texas.gov/resource/8w53-c4f6.json>
- the rule's match window: 2025-09-08 .. 2026-11-12

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136835` — event `109670` — tier `exact`

- stored name: `Meadow Burke, LLC d/b/a Leviat`
- stored count **75**, date `2025-12-02`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Meadow Burke, LLC d/b/a Leviat` — 75 — 2025-12-02 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 84. Job1 USA (San Antonio) (TX)

`warn-tx-2025-10-23-job1` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-10-23**, effective 2025-11-15..2025-11-15
- **31** affected across 2 published row(s)
  - Job1 USA (San Antonio) — 18 — San Antonio, Bexar — `$order=notice_date, $offset=102 within the window filter`
  - Job1 USA (Houston) — 13 — Houston, Harris — `$order=notice_date, $offset=103 within the window filter`
- source: <https://data.texas.gov/resource/8w53-c4f6.json>
- the rule's match window: 2025-09-23 .. 2026-11-27

**5 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136988` — event `109823` — tier `exact`

- stored name: `Job1 USA (San Antonio)`
- stored count **18**, date `2025-11-15`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Job1 USA (San Antonio)` — 18 — 2025-11-15 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `136987` — event `109822` — tier `exact`

- stored name: `Job1 USA (Houston)`
- stored count **13**, date `2025-11-15`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Job1 USA (Houston)` — 13 — 2025-11-15 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Job1 USA (Houston)' differs from the published 'Job1 USA (San Antonio)'

### row `136986` — event `109821` — tier `exact`

- stored name: `Job1 USA (Arlington)`
- stored count **31**, date `2025-11-15`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Job1 USA (Arlington)` — 31 — 2025-11-15 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals the summed notice total
  - row date equals this notice's earliest published effective date
  - stored name 'Job1 USA (Arlington)' differs from the published 'Job1 USA (San Antonio)'

### row `136985` — event `109820` — tier `loose`

- stored name: `Job1 USA (Fort Worth)`
- stored count **25**, date `2025-11-15`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Job1 USA (Fort Worth)` — 25 — 2025-11-15 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 25 matches neither a component row nor the notice total 31
  - row date equals this notice's earliest published effective date
  - stored name 'Job1 USA (Fort Worth)' differs from the published 'Job1 USA (San Antonio)'

### row `136984` — event `109819` — tier `loose`

- stored name: `Job1 USA (Haslet)`
- stored count **25**, date `2025-11-15`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Job1 USA (Haslet)` — 25 — 2025-11-15 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 25 matches neither a component row nor the notice total 31
  - row date equals this notice's earliest published effective date
  - stored name 'Job1 USA (Haslet)' differs from the published 'Job1 USA (San Antonio)'

---

## 85. Wells Fargo & Co. (Lubbock) (TX)

`warn-tx-2025-10-29-wells-fargo` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-10-29**, effective 2025-10-28..2025-10-28
- **225** affected across 1 published row(s)
  - Wells Fargo & Co. (Lubbock) — 225 — Lubbock, Lubbock — `$order=notice_date, $offset=110 within the window filter`
- source: <https://data.texas.gov/resource/8w53-c4f6.json>
- the rule's match window: 2025-09-29 .. 2026-12-03

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `137220` — event `110055` — tier `exact`

- stored name: `Wells Fargo & Co. (Lubbock)`
- stored count **225**, date `2025-10-28`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Wells Fargo & Co. (Lubbock)` — 225 — 2025-10-28 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 86. Apogee Architectural Metals (TX)

`warn-tx-2025-11-05-apogee-architectural-metals` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-11-05**, effective 2026-01-03..2026-01-03
- **58** affected across 1 published row(s)
  - Apogee Architectural Metals — 58 — Mesquite, Dallas — `$order=notice_date, $offset=121 within the window filter`
- source: <https://data.texas.gov/resource/8w53-c4f6.json>
- the rule's match window: 2025-10-06 .. 2026-12-10

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136482` — event `109317` — tier `exact`

- stored name: `Apogee Architectural Metals`
- stored count **58**, date `2026-01-03`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Apogee Architectural Metals` — 58 — 2026-01-03 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 87. FedEx Supply Chain Logistics & Electrronics, Inc. (Coppell) (TX)

`warn-tx-2025-11-25-fedex-supply-chain-logistics` — currently `not_matched`, stratum `large_census`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-11-25**, effective 2026-01-29..2026-01-29
- **856** affected across 1 published row(s)
  - FedEx Supply Chain Logistics & Electrronics, Inc. (Coppell) — 856 — Coppell, Dallas — `$order=notice_date, $offset=130 within the window filter`
- source: <https://data.texas.gov/resource/8w53-c4f6.json>
- the rule's match window: 2025-10-26 .. 2026-12-30

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136269` — event `109104` — tier `exact`

- stored name: `FedEx Supply Chain Logistics & Electrronics, Inc. (Coppell)`
- stored count **856**, date `2026-01-29`, state `TX`, source `warn` / `TX WARN notice`
- live now: `FedEx Supply Chain Logistics & Electrronics, Inc. (Coppell)` — 856 — 2026-01-29 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 88. Tyson Foods, Inc. (Amarillo B-Shift Operations (TX)

`warn-tx-2025-11-26-tyson-foods-amarillo-b` — currently `not_matched`, stratum `large_census`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-11-26**, effective 2026-01-20..2026-01-20
- **1,761** affected across 1 published row(s)
  - Tyson Foods, Inc. (Amarillo B-Shift Operations — 1761 — Amarillo, Potter — `$order=notice_date, $offset=131 within the window filter`
- source: <https://data.texas.gov/resource/8w53-c4f6.json>
- the rule's match window: 2025-10-27 .. 2026-12-31

**2 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136371` — event `109206` — tier `exact`

- stored name: `Tyson Foods, Inc. (Amarillo B-Shift Operations`
- stored count **1761**, date `2026-01-20`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Tyson Foods, Inc. (Amarillo B-Shift Operations` — 1761 — 2026-01-20 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `136079` — event `108914` — tier `exact`

- stored name: `Tyson Foods, Inc (Amarillo B-Shift Operations) Updated`
- stored count **1761**, date `2026-02-24`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Tyson Foods, Inc (Amarillo B-Shift Operations) Updated` — 1761 — 2026-02-24 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is 90 day(s) after the notice date
  - stored name 'Tyson Foods, Inc (Amarillo B-Shift Operations) Updated' differs from the published 'Tyson Foods, Inc. (Amarillo B-Shift Operations'

---

## 89. Yang Ming (America) Corporation Updated (TX)

`warn-tx-2025-12-02-yang-ming-america-updated` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-12-02**, effective 2025-11-30..2025-11-30
- **105** affected across 1 published row(s)
  - Yang Ming (America) Corporation Updated — 105 — Houston, Harris — `$order=notice_date, $offset=132 within the window filter`
- source: <https://data.texas.gov/resource/8w53-c4f6.json>
- the rule's match window: 2025-11-02 .. 2027-01-06

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136887` — event `109722` — tier `exact`

- stored name: `Yang Ming (America) Corporation Updated`
- stored count **105**, date `2025-11-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Yang Ming (America) Corporation Updated` — 105 — 2025-11-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 90. Telvista, Inc. (TX)

`warn-tx-2025-12-26-telvista` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-12-26**, effective 2026-02-28..2026-02-28
- **110** affected across 1 published row(s)
  - Telvista, Inc. — 110 — Dallas, Tarrant — `$order=notice_date, $offset=139 within the window filter`
- source: <https://data.texas.gov/resource/8w53-c4f6.json>
- the rule's match window: 2025-11-26 .. 2027-01-30

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136034` — event `108869` — tier `exact`

- stored name: `Telvista, Inc.`
- stored count **110**, date `2026-02-28`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Telvista, Inc.` — 110 — 2026-02-28 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 91. Tyson Foods, Inc (Amarillo B-Shift Operations) Updated (TX)

`warn-tx-2026-01-20-tyson-foods-amarillo-b` — currently `not_matched`, stratum `primary`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-01-20**, effective 2026-02-24..2026-02-24
- **1,761** affected across 1 published row(s)
  - Tyson Foods, Inc (Amarillo B-Shift Operations) Updated — 1761 — Amarillo, Potter — `$order=notice_date, $offset=145 within the window filter`
- source: <https://data.texas.gov/resource/8w53-c4f6.json>
- the rule's match window: 2025-12-21 .. 2027-02-24

**2 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136079` — event `108914` — tier `exact`

- stored name: `Tyson Foods, Inc (Amarillo B-Shift Operations) Updated`
- stored count **1761**, date `2026-02-24`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Tyson Foods, Inc (Amarillo B-Shift Operations) Updated` — 1761 — 2026-02-24 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `136371` — event `109206` — tier `exact`

- stored name: `Tyson Foods, Inc. (Amarillo B-Shift Operations`
- stored count **1761**, date `2026-01-20`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Tyson Foods, Inc. (Amarillo B-Shift Operations` — 1761 — 2026-01-20 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date is 0 day(s) after the notice date
  - stored name 'Tyson Foods, Inc. (Amarillo B-Shift Operations' differs from the published 'Tyson Foods, Inc (Amarillo B-Shift Operations) Updated'

---

## 92. Compass Connections (TX)

`warn-tx-2026-01-29-compass-connections` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-01-29**, effective 2026-03-29..2026-03-29
- **148** affected across 1 published row(s)
  - Compass Connections — 148 — Harlingen, Cameron — `$order=notice_date, $offset=151 within the window filter`
- source: <https://data.texas.gov/resource/8w53-c4f6.json>
- the rule's match window: 2025-12-30 .. 2027-03-05

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135789` — event `108624` — tier `exact`

- stored name: `Compass Connections`
- stored count **148**, date `2026-03-29`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Compass Connections` — 148 — 2026-03-29 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 93. HGS Solutions (TX)

`warn-tx-2026-02-04-hgs-solutions` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-02-04**, effective 2026-03-31..2026-03-31
- **92** affected across 1 published row(s)
  - HGS Solutions — 92 — El Paso, El Paso — `$order=notice_date, $offset=155 within the window filter`
- source: <https://data.texas.gov/resource/8w53-c4f6.json>
- the rule's match window: 2026-01-05 .. 2027-03-11

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135758` — event `108593` — tier `exact`

- stored name: `HGS Solutions`
- stored count **92**, date `2026-03-31`, state `TX`, source `warn` / `TX WARN notice`
- live now: `HGS Solutions` — 92 — 2026-03-31 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 94. Stockyards Hotel and H3 Ranch (TX)

`warn-tx-2026-02-19-stockyards-hotel-and-h3` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-02-19**, effective 2026-04-06..2026-04-06
- **120** affected across 1 published row(s)
  - Stockyards Hotel and H3 Ranch — 120 — Fort Worth, Tarrant — `$order=notice_date, $offset=161 within the window filter`
- source: <https://data.texas.gov/resource/8w53-c4f6.json>
- the rule's match window: 2026-01-20 .. 2027-03-26

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135636` — event `108471` — tier `exact`

- stored name: `Stockyards Hotel and H3 Ranch`
- stored count **120**, date `2026-04-06`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Stockyards Hotel and H3 Ranch` — 120 — 2026-04-06 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 95. First Brands Group, LLC(Billy Mitchell) (TX)

`warn-tx-2026-03-04-first-brands` — currently `not_matched`, stratum `large_census`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-03-04**, effective 2026-04-30..2026-04-30
- **571** affected across 3 published row(s)
  - First Brands Group, LLC(Billy Mitchell) — 345 — Brownsville, Cameron — `$order=notice_date, $offset=165 within the window filter`
  - First Brands Group, LLC. (Titan Dist. Center) — 183 — Brownsville, Cameron — `$order=notice_date, $offset=166 within the window filter`
  - First Brands Group LLC. (ASC Facility) — 43 — Brownsville, Cameron — `$order=notice_date, $offset=167 within the window filter`
- source: <https://data.texas.gov/resource/8w53-c4f6.json>
- the rule's match window: 2026-02-02 .. 2027-04-08

**3 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135329` — event `108164` — tier `exact`

- stored name: `First Brands Group, LLC(Billy Mitchell)`
- stored count **345**, date `2026-04-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `First Brands Group, LLC(Billy Mitchell)` — 345 — 2026-04-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `135328` — event `108163` — tier `exact`

- stored name: `First Brands Group, LLC. (Titan Dist. Center)`
- stored count **183**, date `2026-04-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `First Brands Group, LLC. (Titan Dist. Center)` — 183 — 2026-04-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'First Brands Group, LLC. (Titan Dist. Center)' differs from the published 'First Brands Group, LLC(Billy Mitchell)'

### row `135327` — event `108162` — tier `exact`

- stored name: `First Brands Group LLC. (ASC Facility)`
- stored count **43**, date `2026-04-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `First Brands Group LLC. (ASC Facility)` — 43 — 2026-04-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'First Brands Group LLC. (ASC Facility)' differs from the published 'First Brands Group, LLC(Billy Mitchell)'

---

## 96. Albertsons #4286 (W. Freeway) (TX)

`warn-tx-2026-03-25-albertsons-4286` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-03-25**, effective 2026-04-25..2026-04-25
- **56** affected across 1 published row(s)
  - Albertsons #4286 (W. Freeway) — 56 — Fort Worth, Tarrant — `$order=notice_date, $offset=171 within the window filter`
- source: <https://data.texas.gov/resource/8w53-c4f6.json>
- the rule's match window: 2026-02-23 .. 2027-04-29

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135435` — event `108270` — tier `exact`

- stored name: `Albertsons #4286 (W. Freeway)`
- stored count **56**, date `2026-04-25`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Albertsons #4286 (W. Freeway)` — 56 — 2026-04-25 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 97. DSV Contract Logistics (3PL Logistics Facility) (TX)

`warn-tx-2026-04-02-dsv-contract-logistics` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-04-02**, effective 2026-04-30..2026-04-30
- **391** affected across 1 published row(s)
  - DSV Contract Logistics (3PL Logistics Facility) — 391 — Wilmer, Dallas — `$order=notice_date, $offset=177 within the window filter`
- source: <https://data.texas.gov/resource/8w53-c4f6.json>
- the rule's match window: 2026-03-03 .. 2027-05-07

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135326` — event `108161` — tier `exact`

- stored name: `DSV Contract Logistics (3PL Logistics Facility)`
- stored count **391**, date `2026-04-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `DSV Contract Logistics (3PL Logistics Facility)` — 391 — 2026-04-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 98. National Safety Apparel, LLC (TX)

`warn-tx-2026-04-23-national-safety-apparel` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-04-23**, effective 2026-06-30..2026-06-30
- **50** affected across 1 published row(s)
  - National Safety Apparel, LLC — 50 — San Antonio, Bexar — `$order=notice_date, $offset=191 within the window filter`
- source: <https://data.texas.gov/resource/8w53-c4f6.json>
- the rule's match window: 2026-03-24 .. 2027-05-28

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `134623` — event `107458` — tier `exact`

- stored name: `National Safety Apparel, LLC`
- stored count **50**, date `2026-06-30`, state `TX`, source `warn` / `TX WARN notice`
- live now: `National Safety Apparel, LLC` — 50 — 2026-06-30 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 99. Republic National Distributing Company, LLC (Reyes Holdings, L.L.C) Austin (TX)

`warn-tx-2026-04-23-republic-national-distributing-reyes` — currently `not_matched`, stratum `large_census`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-04-23**, effective 2026-06-21..2026-06-21
- **1,903** affected across 5 published row(s)
  - Republic National Distributing Company, LLC (Reyes Holdings, L.L.C) Austin — 164 — Austin, Travis — `$order=notice_date, $offset=186 within the window filter`
  - Republic National Distributing Company, LLC (Reyes Holdings, L.L.C) Corpus Christie — 90 — Corpus Ch, Nueces — `$order=notice_date, $offset=187 within the window filter`
  - Republic National Distributing Company, LLC (Reyes Holdings, L.L.C) Grand Prairie — 689 — Grand Prairie, Tarrant — `$order=notice_date, $offset=188 within the window filter`
  - Republic National Distributing Company, LLC (Reyes Holdings, L.L.C) Houston — 588 — Houston, Harris — `$order=notice_date, $offset=189 within the window filter`
  - Republic National Distributing Company, LLC (Reyes Holdings, L.L.C) San Antonio — 372 — Schertz, Bexar — `$order=notice_date, $offset=190 within the window filter`
- source: <https://data.texas.gov/resource/8w53-c4f6.json>
- the rule's match window: 2026-03-24 .. 2027-05-28

**5 candidate row(s).** Each block below is one row and says nothing about any other.

### row `134749` — event `107584` — tier `exact`

- stored name: `Republic National Distributing Company, LLC (Reyes Holdings, L.L.C) Austin`
- stored count **164**, date `2026-06-21`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Republic National Distributing Company, LLC (Reyes Holdings, L.L.C) Austin` — 164 — 2026-06-21 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `134748` — event `107583` — tier `exact`

- stored name: `Republic National Distributing Company, LLC (Reyes Holdings, L.L.C) Corpus Christie`
- stored count **90**, date `2026-06-21`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Republic National Distributing Company, LLC (Reyes Holdings, L.L.C) Corpus Christie` — 90 — 2026-06-21 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Republic National Distributing Company, LLC (Reyes Holdings, L.L.C) Corpus Christie' differs from the published 'Republic National Distributing Company, LLC (Reyes Holdings, L.L.C) Austin'

### row `134747` — event `107582` — tier `exact`

- stored name: `Republic National Distributing Company, LLC (Reyes Holdings, L.L.C) Grand Prairie`
- stored count **689**, date `2026-06-21`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Republic National Distributing Company, LLC (Reyes Holdings, L.L.C) Grand Prairie` — 689 — 2026-06-21 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Republic National Distributing Company, LLC (Reyes Holdings, L.L.C) Grand Prairie' differs from the published 'Republic National Distributing Company, LLC (Reyes Holdings, L.L.C) Austin'

### row `134746` — event `107581` — tier `exact`

- stored name: `Republic National Distributing Company, LLC (Reyes Holdings, L.L.C) Houston`
- stored count **588**, date `2026-06-21`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Republic National Distributing Company, LLC (Reyes Holdings, L.L.C) Houston` — 588 — 2026-06-21 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Republic National Distributing Company, LLC (Reyes Holdings, L.L.C) Houston' differs from the published 'Republic National Distributing Company, LLC (Reyes Holdings, L.L.C) Austin'

### row `134745` — event `107580` — tier `exact`

- stored name: `Republic National Distributing Company, LLC (Reyes Holdings, L.L.C) San Antonio`
- stored count **372**, date `2026-06-21`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Republic National Distributing Company, LLC (Reyes Holdings, L.L.C) San Antonio` — 372 — 2026-06-21 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Republic National Distributing Company, LLC (Reyes Holdings, L.L.C) San Antonio' differs from the published 'Republic National Distributing Company, LLC (Reyes Holdings, L.L.C) Austin'

---

## 100. Laurel Ridge Treatment Center (Laurel Ridge) (TX)

`warn-tx-2026-04-27-laurel-ridge-treatment-center` — currently `not_matched`, stratum `large_census`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-04-27**, effective 2026-06-26..2026-06-26
- **648** affected across 1 published row(s)
  - Laurel Ridge Treatment Center (Laurel Ridge) — 648 — San Antonio, Bexar — `$order=notice_date, $offset=193 within the window filter`
- source: <https://data.texas.gov/resource/8w53-c4f6.json>
- the rule's match window: 2026-03-28 .. 2027-06-01

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `134698` — event `107533` — tier `exact`

- stored name: `Laurel Ridge Treatment Center (Laurel Ridge)`
- stored count **648**, date `2026-06-26`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Laurel Ridge Treatment Center (Laurel Ridge)` — 648 — 2026-06-26 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

---

## 101. Spirit Airlines (IAH) May 2026 (TX)

`warn-tx-2026-05-02-spirit-airlines-iah-may` — currently `not_matched`, stratum `large_census`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-05-02**, effective 2026-05-02..2026-05-02
- **515** affected across 1 published row(s)
  - Spirit Airlines (IAH) May 2026 — 515 — Houston, Harris — `$order=notice_date, $offset=196 within the window filter`
- source: <https://data.texas.gov/resource/8w53-c4f6.json>
- the rule's match window: 2026-04-02 .. 2027-06-06

**2 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135253` — event `108088` — tier `exact`

- stored name: `Spirit Airlines (IAH) May 2026`
- stored count **515**, date `2026-05-02`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Spirit Airlines (IAH) May 2026` — 515 — 2026-05-02 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date

### row `135252` — event `108087` — tier `loose`

- stored name: `Spirit Airlines (DFW) May 2026`
- stored count **444**, date `2026-05-02`, state `TX`, source `warn` / `TX WARN notice`
- live now: `Spirit Airlines (DFW) May 2026` — 444 — 2026-05-02 — `warn`
- our cited source: <https://data.texas.gov/d/8w53-c4f6>
- flags for this row:
  - job_count 444 matches neither a component row nor the notice total 515
  - row date equals this notice's earliest published effective date
  - stored name 'Spirit Airlines (DFW) May 2026' differs from the published 'Spirit Airlines (IAH) May 2026'

---

## 102. QB Intermediate Holdings, LLC, Quality Built, LLC, Foresite Technology Solutions, LLC (f/k/a QB Technology Co., LLC), SMC Systems LLC (d/b/a SkyeTec), SkyeTec Engineering Services, LLC, and DuctTesters, Inc. 9570 Regency Square Blvd Suite 410 JACKSONVILLE, FL, 32225 (FL)

`warn-fl-2025-07-07-qb-intermediate-quality-built` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-07-07**, effective 2025-07-03..2025-07-03
- **70** affected across 2 published row(s)
  - QB Intermediate Holdings, LLC, Quality Built, LLC, Foresite Technology Solutions, LLC (f/k/a QB Technology Co., LLC), SMC Systems LLC (d/b/a SkyeTec), SkyeTec Engineering Services, LLC, and DuctTesters, Inc. 9570 Regency Square Blvd Suite 410 JACKSONVILLE, FL, 32225 — 20 — no location published — `year=2025 page=1 row 94`
  - QB Intermediate Holdings, LLC, Quality Built, LLC, Foresite Technology Solutions, LLC (f/k/a QB Technology Co., LLC), SMC Systems LLC (d/b/a SkyeTec), SkyeTec Engineering Services, LLC, and DuctTesters, Inc. 633 S. Andrews Ave FORT LAUDERDALE, FL, 33301 — 50 — no location published — `year=2025 page=2 row 54`
- source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2025&page=1>
- the rule's match window: 2025-06-07 .. 2026-08-11

**2 candidate row(s).** Each block below is one row and says nothing about any other.

### row `138283` — event `111118` — tier `exact`

- stored name: `QB Intermediate Holdings, LLC, Quality Built, LLC, Foresite Technology Solutions, LLC (f/k/a QB Technology Co., LLC), SMC Systems LLC (d/b/a SkyeTec), SkyeTec Engineering Services, LLC, and DuctTesters, Inc.`
- stored count **50**, date `2025-07-03`, state `FL`, source `warn` / `FL WARN notice`
- live now: `QB Intermediate Holdings, LLC, Quality Built, LLC, Foresite Technology Solutions, LLC (f/k/a QB Technology Co., LLC), SMC Systems LLC (d/b/a SkyeTec), SkyeTec Engineering Services, LLC, and DuctTesters, Inc.` — 50 — 2025-07-03 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'QB Intermediate Holdings, LLC, Quality Built, LLC, Foresite Technology Solutions, LLC (f/k/a QB Technology Co., LLC), SMC Systems LLC (d/b/a SkyeTec), SkyeTec Engineering Services, LLC, and DuctTesters, Inc.' differs from the published 'QB Intermediate Holdings, LLC, Quality Built, LLC, Foresite Technology Solutions, LLC (f/k/a QB Technology Co., LLC), SMC Systems LLC (d/b/a SkyeTec), SkyeTec Engineering Services, LLC, and DuctTesters, Inc. 9570 Regency Square Blvd Suite 410 JACKSONVILLE, FL, 32225'

### row `138282` — event `111117` — tier `exact`

- stored name: `QB Intermediate Holdings, LLC, Quality Built, LLC, Foresite Technology Solutions, LLC (f/k/a QB Technology Co., LLC), SMC Systems LLC (d/b/a SkyeTec), SkyeTec Engineering Services, LLC, and DuctTesters, Inc.`
- stored count **20**, date `2025-07-03`, state `FL`, source `warn` / `FL WARN notice`
- live now: `QB Intermediate Holdings, LLC, Quality Built, LLC, Foresite Technology Solutions, LLC (f/k/a QB Technology Co., LLC), SMC Systems LLC (d/b/a SkyeTec), SkyeTec Engineering Services, LLC, and DuctTesters, Inc.` — 20 — 2025-07-03 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'QB Intermediate Holdings, LLC, Quality Built, LLC, Foresite Technology Solutions, LLC (f/k/a QB Technology Co., LLC), SMC Systems LLC (d/b/a SkyeTec), SkyeTec Engineering Services, LLC, and DuctTesters, Inc.' differs from the published 'QB Intermediate Holdings, LLC, Quality Built, LLC, Foresite Technology Solutions, LLC (f/k/a QB Technology Co., LLC), SMC Systems LLC (d/b/a SkyeTec), SkyeTec Engineering Services, LLC, and DuctTesters, Inc. 9570 Regency Square Blvd Suite 410 JACKSONVILLE, FL, 32225'

---

## 103. Carroll Fulmer Logistics Corporation 8340 American Way GROVELAND, FL, 34736 (FL)

`warn-fl-2025-07-29-carroll-fulmer-logistics` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-07-29**, effective 2025-09-27..2025-09-27
- **330** affected across 1 published row(s)
  - Carroll Fulmer Logistics Corporation 8340 American Way GROVELAND, FL, 34736 — 330 — no location published — `year=2025 page=1 row 77`
- source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2025&page=1>
- the rule's match window: 2025-06-29 .. 2026-09-02

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `137541` — event `110376` — tier `exact`

- stored name: `Carroll Fulmer Logistics Corporation`
- stored count **330**, date `2025-09-27`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Carroll Fulmer Logistics Corporation` — 330 — 2025-09-27 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Carroll Fulmer Logistics Corporation' differs from the published 'Carroll Fulmer Logistics Corporation 8340 American Way GROVELAND, FL, 34736'

---

## 104. Pasa Services, Inc. d/b/a Flamingo Graphics 13015 NW 38th Avenue OPA LOCKA, FL, 33054 (FL)

`warn-fl-2025-08-08-pasa-services-d-b` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-08-08**, effective 2025-10-09..2025-10-09
- **36** affected across 1 published row(s)
  - Pasa Services, Inc. d/b/a Flamingo Graphics 13015 NW 38th Avenue OPA LOCKA, FL, 33054 — 36 — no location published — `year=2025 page=1 row 74`
- source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2025&page=1>
- the rule's match window: 2025-07-09 .. 2026-09-12

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `137329` — event `110164` — tier `exact`

- stored name: `Pasa Services, Inc. d/b/a Flamingo Graphics`
- stored count **36**, date `2025-10-09`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Pasa Services, Inc. d/b/a Flamingo Graphics` — 36 — 2025-10-09 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Pasa Services, Inc. d/b/a Flamingo Graphics' differs from the published 'Pasa Services, Inc. d/b/a Flamingo Graphics 13015 NW 38th Avenue OPA LOCKA, FL, 33054'

---

## 105. Tata Consultancy Services, Ltd 550 Water Street JACKSONVILLE, FL, 32202 (FL)

`warn-fl-2025-08-19-tata-consultancy-services` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-08-19**, effective 2025-10-18..2025-10-18
- **58** affected across 1 published row(s)
  - Tata Consultancy Services, Ltd 550 Water Street JACKSONVILLE, FL, 32202 — 58 — no location published — `year=2025 page=1 row 69`
- source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2025&page=1>
- the rule's match window: 2025-07-20 .. 2026-09-23

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `137279` — event `110114` — tier `exact`

- stored name: `Tata Consultancy Services, Ltd`
- stored count **58**, date `2025-10-18`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Tata Consultancy Services, Ltd` — 58 — 2025-10-18 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Tata Consultancy Services, Ltd' differs from the published 'Tata Consultancy Services, Ltd 550 Water Street JACKSONVILLE, FL, 32202'

---

## 106. Essendant 2405 Commerce Park Dr ORLANDO, FL, 32819 (FL)

`warn-fl-2025-09-04-essendant` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-09-04**, effective 2025-12-31..2025-12-31
- **73** affected across 1 published row(s)
  - Essendant 2405 Commerce Park Dr ORLANDO, FL, 32819 — 73 — no location published — `year=2025 page=1 row 60`
- source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2025&page=1>
- the rule's match window: 2025-08-05 .. 2026-10-09

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136616` — event `109451` — tier `exact`

- stored name: `Essendant`
- stored count **73**, date `2025-12-31`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Essendant` — 73 — 2025-12-31 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Essendant' differs from the published 'Essendant 2405 Commerce Park Dr ORLANDO, FL, 32819'

---

## 107. Spirit Airlines Miami International Airport located at 4200 NW 42nd Avenue MIAMI, FL, 33142 (FL)

`warn-fl-2025-09-25-spirit-airlines-miami-international` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-09-25**, effective 2025-12-01..2025-12-01
- **71** affected across 1 published row(s)
  - Spirit Airlines Miami International Airport located at 4200 NW 42nd Avenue MIAMI, FL, 33142 — 71 — no location published — `year=2025 page=1 row 51`
- source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2025&page=1>
- the rule's match window: 2025-08-26 .. 2026-10-30

**9 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136856` — event `109691` — tier `exact`

- stored name: `Spirit Airlines`
- stored count **71**, date `2025-12-01`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Spirit Airlines` — 71 — 2025-12-01 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Miami International Airport located at 4200 NW 42nd Avenue MIAMI, FL, 33142'

### row `136859` — event `109694` — tier `loose`

- stored name: `Spirit Airlines`
- stored count **100**, date `2025-12-01`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Spirit Airlines` — 100 — 2025-12-01 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count 100 matches neither a component row nor the notice total 71
  - row date equals this notice's earliest published effective date
  - stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Miami International Airport located at 4200 NW 42nd Avenue MIAMI, FL, 33142'

### row `136858` — event `109693` — tier `loose`

- stored name: `Spirit Airlines`
- stored count **309**, date `2025-12-01`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Spirit Airlines` — 309 — 2025-12-01 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count 309 matches neither a component row nor the notice total 71
  - row date equals this notice's earliest published effective date
  - stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Miami International Airport located at 4200 NW 42nd Avenue MIAMI, FL, 33142'

### row `136857` — event `109692` — tier `loose`

- stored name: `Spirit Airlines`
- stored count **350**, date `2025-12-01`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Spirit Airlines` — 350 — 2025-12-01 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count 350 matches neither a component row nor the notice total 71
  - row date equals this notice's earliest published effective date
  - stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Miami International Airport located at 4200 NW 42nd Avenue MIAMI, FL, 33142'

### row `135257` — event `108092` — tier `loose`

- stored name: `Spirit Airlines`
- stored count **551**, date `2026-05-02`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Spirit Airlines` — 551 — 2026-05-02 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count 551 matches neither a component row nor the notice total 71
  - row date is 219 day(s) after the notice date
  - stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Miami International Airport located at 4200 NW 42nd Avenue MIAMI, FL, 33142'

### row `135256` — event `108091` — tier `loose`

- stored name: `Spirit Airlines`
- stored count **181**, date `2026-05-02`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Spirit Airlines` — 181 — 2026-05-02 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count 181 matches neither a component row nor the notice total 71
  - row date is 219 day(s) after the notice date
  - stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Miami International Airport located at 4200 NW 42nd Avenue MIAMI, FL, 33142'

### row `135255` — event `108090` — tier `loose`

- stored name: `Spirit Airlines`
- stored count **796**, date `2026-05-02`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Spirit Airlines` — 796 — 2026-05-02 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count 796 matches neither a component row nor the notice total 71
  - row date is 219 day(s) after the notice date
  - stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Miami International Airport located at 4200 NW 42nd Avenue MIAMI, FL, 33142'

### row `135254` — event `108089` — tier `loose`

- stored name: `Spirit Airlines`
- stored count **2529**, date `2026-05-02`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Spirit Airlines` — 2529 — 2026-05-02 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count 2529 matches neither a component row nor the notice total 71
  - row date is 219 day(s) after the notice date
  - stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Miami International Airport located at 4200 NW 42nd Avenue MIAMI, FL, 33142'

### row `176452` — event `149196` — tier `loose`

- stored name: `Spirit Airlines`
- stored count **4000**, date `2026-05-05`, state `FL`, source `news` / `NBC 6 South Florida`
- live now: `Spirit Airlines` — 4000 — 2026-05-05 — `news`
- our cited source: <https://news.google.com/rss/articles/CBMiwwFBVV95cUxQMFM4YWZsUl96aTJiX2FLQldmUlVZbUo5U1dNakxBazAwRC1zZ0RwaXZDVFRKVmU0MlhfOWlxRnhPLVd2b2dWaWtRT0tMSFJzSnJWMDBEUUxIRlpNWlVaOEUxZWN3SlpQdHFnZjcxdlliNjA0eTUxQ1dqakVpRVZYOUVxdms3Z0hWRXhwZy1YWkxUb0ExZ0VJeXJDWW9xTVJqRThpTkVvS1k4YWt5SjZTampva3RsTTd0WmtJRGRLb0pUY2vSAcsBQVVfeXFMTjRLc3ZQdU1XdWZoZmJHb3pENEphMDdyc19XVlR5LU5fdnl6NkQwLUJyT1hYZm9FbVluX0k1azdDWG1LTk1aZjlWVHpBMk9Kbmp3cEEwbkZLRUdxVUtJa09nWW5tTENIOGxCR2dIWFBjaUVDaDNEVmRoRDlnTnJUWUpDajlZeTIzaS01by1GaFFLTUlCVHQ2WWFnZDhPMVQ3UlVxSkF6cXJmeHpZNGpRdHhldDdMUWlpUlhNZ0VlNGtzNlI4WGVvdnNuLTQ?oc=5>
- flags for this row:
  - row source is news/filing, not a WARN-tier row
  - job_count 4000 matches neither a component row nor the notice total 71
  - row date is 222 day(s) after the notice date
  - stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Miami International Airport located at 4200 NW 42nd Avenue MIAMI, FL, 33142'

---

## 108. ID Logistics 2007 Gandy Blvd. N SAINT PETERSBURG, FL, 33702 (FL)

`warn-fl-2025-10-02-id-logistics` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-10-02**, effective 2025-12-14..2025-12-14
- **174** affected across 2 published row(s)
  - ID Logistics 2007 Gandy Blvd. N SAINT PETERSBURG, FL, 33702 — 55 — no location published — `year=2025 page=1 row 46`
  - ID Logistics 2005 Gandy Blvd. N SAINT PETERSBURG, FL, 33702 — 119 — no location published — `year=2025 page=1 row 47`
- source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2025&page=1>
- the rule's match window: 2025-09-02 .. 2026-11-06

**2 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136751` — event `109586` — tier `exact`

- stored name: `ID Logistics`
- stored count **119**, date `2025-12-14`, state `FL`, source `warn` / `FL WARN notice`
- live now: `ID Logistics` — 119 — 2025-12-14 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'ID Logistics' differs from the published 'ID Logistics 2007 Gandy Blvd. N SAINT PETERSBURG, FL, 33702'

### row `136750` — event `109585` — tier `exact`

- stored name: `ID Logistics`
- stored count **55**, date `2025-12-14`, state `FL`, source `warn` / `FL WARN notice`
- live now: `ID Logistics` — 55 — 2025-12-14 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'ID Logistics' differs from the published 'ID Logistics 2007 Gandy Blvd. N SAINT PETERSBURG, FL, 33702'

---

## 109. Reworld Projects, LLC 3001 110th Ave. N SAINT PETERSBURG, FL, 33716 (FL)

`warn-fl-2025-10-10-reworld-projects` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-10-10**, effective 2025-12-31..2025-12-31
- **70** affected across 1 published row(s)
  - Reworld Projects, LLC 3001 110th Ave. N SAINT PETERSBURG, FL, 33716 — 70 — no location published — `year=2025 page=1 row 43`
- source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2025&page=1>
- the rule's match window: 2025-09-10 .. 2026-11-14

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136617` — event `109452` — tier `exact`

- stored name: `Reworld Projects, LLC`
- stored count **70**, date `2025-12-31`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Reworld Projects, LLC` — 70 — 2025-12-31 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Reworld Projects, LLC' differs from the published 'Reworld Projects, LLC 3001 110th Ave. N SAINT PETERSBURG, FL, 33716'

---

## 110. Eulen Aviation 2100 NW 42nd Ave MIAMI, FL, 33142 (FL)

`warn-fl-2025-10-23-eulen-aviation` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-10-23**, effective 2025-12-06..2025-12-06
- **100** affected across 1 published row(s)
  - Eulen Aviation 2100 NW 42nd Ave MIAMI, FL, 33142 — 100 — no location published — `year=2025 page=1 row 34`
- source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2025&page=1>
- the rule's match window: 2025-09-23 .. 2026-11-27

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136804` — event `109639` — tier `exact`

- stored name: `Eulen Aviation`
- stored count **100**, date `2025-12-06`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Eulen Aviation` — 100 — 2025-12-06 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Eulen Aviation' differs from the published 'Eulen Aviation 2100 NW 42nd Ave MIAMI, FL, 33142'

---

## 111. Frito-Lay, Inc 2000 Parks Oaks Avenue ORLANDO, FL, 32808 (FL)

`warn-fl-2025-11-04-frito-lay` — currently `not_matched`, stratum `primary`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-11-04**, effective 2025-11-04..2025-11-04
- **500** affected across 2 published row(s)
  - Frito-Lay, Inc 2000 Parks Oaks Avenue ORLANDO, FL, 32808 — 46 — no location published — `year=2025 page=1 row 27`
  - Frito-Lay, Inc 2800 Silver Star Road ORLANDO, FL, 32808 — 454 — no location published — `year=2025 page=1 row 28`
- source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2025&page=1>
- the rule's match window: 2025-10-05 .. 2026-12-09

**2 candidate row(s).** Each block below is one row and says nothing about any other.

### row `137101` — event `109936` — tier `exact`

- stored name: `Frito-Lay, Inc`
- stored count **454**, date `2025-11-04`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Frito-Lay, Inc` — 454 — 2025-11-04 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Frito-Lay, Inc' differs from the published 'Frito-Lay, Inc 2000 Parks Oaks Avenue ORLANDO, FL, 32808'

### row `137100` — event `109935` — tier `exact`

- stored name: `Frito-Lay, Inc`
- stored count **46**, date `2025-11-04`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Frito-Lay, Inc` — 46 — 2025-11-04 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Frito-Lay, Inc' differs from the published 'Frito-Lay, Inc 2000 Parks Oaks Avenue ORLANDO, FL, 32808'

---

## 112. Hudson 1 Jeff Fuqua Blvd ORLANDO, FL, 32827 (FL)

`warn-fl-2025-11-18-hudson` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-11-18**, effective 2026-01-23..2026-01-23
- **133** affected across 1 published row(s)
  - Hudson 1 Jeff Fuqua Blvd ORLANDO, FL, 32827 — 133 — no location published — `year=2025 page=1 row 18`
- source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2025&page=1>
- the rule's match window: 2025-10-19 .. 2026-12-23

**2 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136359` — event `109194` — tier `exact`

- stored name: `Hudson`
- stored count **133**, date `2026-01-23`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Hudson` — 133 — 2026-01-23 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Hudson' differs from the published 'Hudson 1 Jeff Fuqua Blvd ORLANDO, FL, 32827'

### row `136659` — event `109494` — tier `loose`

- stored name: `Hudson`
- stored count **14**, date `2025-12-28`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Hudson` — 14 — 2025-12-28 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count 14 matches neither a component row nor the notice total 133
  - row date is 40 day(s) after the notice date
  - stored name 'Hudson' differs from the published 'Hudson 1 Jeff Fuqua Blvd ORLANDO, FL, 32827'

---

## 113. Kroger Fulfillment Network LLC Kroger Tampa Fulfillment Center, 1820 Massaro Blvd TAMPA, FL, 33619 (FL)

`warn-fl-2025-11-18-kroger-fulfillment-network-kroger` — currently `not_matched`, stratum `large_census`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-11-18**, effective 2026-02-01..2026-02-01
- **1,350** affected across 3 published row(s)
  - Kroger Fulfillment Network LLC Kroger Tampa Fulfillment Center, 1820 Massaro Blvd TAMPA, FL, 33619 — 234 — no location published — `year=2025 page=1 row 21`
  - Kroger Fulfillment Network LLC, Kroger Fulfillment Network LLC, 1 Imerson Park Blvd Building 200 JACKSONVILLE, FL, 32219 — 181 — no location published — `year=2025 page=1 row 22`
  - Kroger Fulfillment Network LLC Kroger Delivery Fulfillment Center,7925 American Way GROVELAND, FL, 34736 — 935 — no location published — `year=2025 page=1 row 23`
- source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2025&page=1>
- the rule's match window: 2025-10-19 .. 2026-12-23

**4 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136219` — event `109054` — tier `exact`

- stored name: `Kroger Fulfillment Network LLC`
- stored count **935**, date `2026-02-01`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Kroger Fulfillment Network LLC` — 935 — 2026-02-01 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Kroger Fulfillment Network LLC' differs from the published 'Kroger Fulfillment Network LLC Kroger Tampa Fulfillment Center, 1820 Massaro Blvd TAMPA, FL, 33619'

### row `136218` — event `109053` — tier `exact`

- stored name: `Kroger Fulfillment Network LLC`
- stored count **181**, date `2026-02-01`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Kroger Fulfillment Network LLC` — 181 — 2026-02-01 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Kroger Fulfillment Network LLC' differs from the published 'Kroger Fulfillment Network LLC Kroger Tampa Fulfillment Center, 1820 Massaro Blvd TAMPA, FL, 33619'

### row `136217` — event `109052` — tier `exact`

- stored name: `Kroger Fulfillment Network LLC`
- stored count **234**, date `2026-02-01`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Kroger Fulfillment Network LLC` — 234 — 2026-02-01 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Kroger Fulfillment Network LLC' differs from the published 'Kroger Fulfillment Network LLC Kroger Tampa Fulfillment Center, 1820 Massaro Blvd TAMPA, FL, 33619'

### row `136216` — event `109051` — tier `loose`

- stored name: `Kroger Fulfillment Network LLC`
- stored count **53**, date `2026-02-01`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Kroger Fulfillment Network LLC` — 53 — 2026-02-01 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count 53 matches neither a component row nor the notice total 1350
  - row date equals this notice's earliest published effective date
  - stored name 'Kroger Fulfillment Network LLC' differs from the published 'Kroger Fulfillment Network LLC Kroger Tampa Fulfillment Center, 1820 Massaro Blvd TAMPA, FL, 33619'

---

## 114. Sodexo, Inc and Affiliates Miami Jewish Health 5200 NE 2nd Ave MIAMI, FL, 33137 (FL)

`warn-fl-2025-11-22-sodexo-and-affiliates-miami` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-11-22**, effective 2026-02-28..2026-02-28
- **163** affected across 1 published row(s)
  - Sodexo, Inc and Affiliates Miami Jewish Health 5200 NE 2nd Ave MIAMI, FL, 33137 — 163 — no location published — `year=2025 page=1 row 12`
- source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2025&page=1>
- the rule's match window: 2025-10-23 .. 2026-12-27

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136035` — event `108870` — tier `exact`

- stored name: `Sodexo, Inc and Affiliates`
- stored count **163**, date `2026-02-28`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Sodexo, Inc and Affiliates` — 163 — 2026-02-28 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Sodexo, Inc and Affiliates' differs from the published 'Sodexo, Inc and Affiliates Miami Jewish Health 5200 NE 2nd Ave MIAMI, FL, 33137'

---

## 115. Railcrew Xpress 1718-1 North McDuff Avenue JACKSONVILLE, FL, 32254 (FL)

`warn-fl-2025-12-22-railcrew-xpress` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-12-22**, effective 2026-02-27..2026-02-27
- **79** affected across 5 published row(s)
  - Railcrew Xpress 1718-1 North McDuff Avenue JACKSONVILLE, FL, 32254 — 34 — no location published — `year=2025 page=1 row 1`
  - Railcrew Xpress 9400 NW 37th Avenue MIAMI, FL, 33147 — 4 — no location published — `year=2025 page=1 row 2`
  - Railcrew Xpress 450 Seaboard Road MULBERRY, FL, 33860 — 24 — no location published — `year=2025 page=1 row 3`
  - Railcrew Xpress 415 East Landstreet Road ORLANDO, FL, 32824 — 7 — no location published — `year=2025 page=1 row 4`
  - Railcrew Xpress 5656 East Adamo Drive TAMPA, FL, 33619 — 10 — no location published — `year=2025 page=1 row 5`
- source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2025&page=1>
- the rule's match window: 2025-11-22 .. 2027-01-26

**5 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136058` — event `108893` — tier `exact`

- stored name: `Railcrew Xpress`
- stored count **10**, date `2026-02-27`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Railcrew Xpress` — 10 — 2026-02-27 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Railcrew Xpress' differs from the published 'Railcrew Xpress 1718-1 North McDuff Avenue JACKSONVILLE, FL, 32254'

### row `136057` — event `108892` — tier `exact`

- stored name: `Railcrew Xpress`
- stored count **7**, date `2026-02-27`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Railcrew Xpress` — 7 — 2026-02-27 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Railcrew Xpress' differs from the published 'Railcrew Xpress 1718-1 North McDuff Avenue JACKSONVILLE, FL, 32254'

### row `136056` — event `108891` — tier `exact`

- stored name: `Railcrew Xpress`
- stored count **24**, date `2026-02-27`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Railcrew Xpress` — 24 — 2026-02-27 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Railcrew Xpress' differs from the published 'Railcrew Xpress 1718-1 North McDuff Avenue JACKSONVILLE, FL, 32254'

### row `136055` — event `108890` — tier `exact`

- stored name: `Railcrew Xpress`
- stored count **4**, date `2026-02-27`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Railcrew Xpress` — 4 — 2026-02-27 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Railcrew Xpress' differs from the published 'Railcrew Xpress 1718-1 North McDuff Avenue JACKSONVILLE, FL, 32254'

### row `136054` — event `108889` — tier `exact`

- stored name: `Railcrew Xpress`
- stored count **34**, date `2026-02-27`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Railcrew Xpress` — 34 — 2026-02-27 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Railcrew Xpress' differs from the published 'Railcrew Xpress 1718-1 North McDuff Avenue JACKSONVILLE, FL, 32254'

---

## 116. SMBC MANUBANK Bradenton 515 South Figueroa Street Los Angeles, CA 90071 BRADENTON, FL, 34207 (FL)

`warn-fl-2026-01-08-smbc-manubank-bradenton` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-01-08**, effective 2026-03-10..2026-03-10
- **1** affected across 1 published row(s)
  - SMBC MANUBANK Bradenton 515 South Figueroa Street Los Angeles, CA 90071 BRADENTON, FL, 34207 — 1 — no location published — `year=2026 page=2 row 92`
- source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026&page=2>
- the rule's match window: 2025-12-09 .. 2027-02-12

**2 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135930` — event `108765` — tier `exact`

- stored name: `SMBC MANUBANK`
- stored count **1**, date `2026-03-10`, state `FL`, source `warn` / `FL WARN notice`
- live now: `SMBC MANUBANK` — 1 — 2026-03-10 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'SMBC MANUBANK' differs from the published 'SMBC MANUBANK Bradenton 515 South Figueroa Street Los Angeles, CA 90071 BRADENTON, FL, 34207'

### row `135931` — event `108766` — tier `loose`

- stored name: `SMBC MANUBANK`
- stored count **4**, date `2026-03-10`, state `FL`, source `warn` / `FL WARN notice`
- live now: `SMBC MANUBANK` — 4 — 2026-03-10 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count 4 matches neither a component row nor the notice total 1
  - row date equals this notice's earliest published effective date
  - stored name 'SMBC MANUBANK' differs from the published 'SMBC MANUBANK Bradenton 515 South Figueroa Street Los Angeles, CA 90071 BRADENTON, FL, 34207'

---

## 117. SMBC MANUBANK Marco Island 515 South Figueroa Street Los Angeles, CA 90071 MARCO ISLAND, FL, 34145 (FL)

`warn-fl-2026-01-08-smbc-manubank-marco-island` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-01-08**, effective 2026-03-10..2026-03-10
- **1** affected across 1 published row(s)
  - SMBC MANUBANK Marco Island 515 South Figueroa Street Los Angeles, CA 90071 MARCO ISLAND, FL, 34145 — 1 — no location published — `year=2026 page=2 row 88`
- source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026&page=2>
- the rule's match window: 2025-12-09 .. 2027-02-12

**2 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135930` — event `108765` — tier `exact`

- stored name: `SMBC MANUBANK`
- stored count **1**, date `2026-03-10`, state `FL`, source `warn` / `FL WARN notice`
- live now: `SMBC MANUBANK` — 1 — 2026-03-10 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'SMBC MANUBANK' differs from the published 'SMBC MANUBANK Marco Island 515 South Figueroa Street Los Angeles, CA 90071 MARCO ISLAND, FL, 34145'

### row `135931` — event `108766` — tier `loose`

- stored name: `SMBC MANUBANK`
- stored count **4**, date `2026-03-10`, state `FL`, source `warn` / `FL WARN notice`
- live now: `SMBC MANUBANK` — 4 — 2026-03-10 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count 4 matches neither a component row nor the notice total 1
  - row date equals this notice's earliest published effective date
  - stored name 'SMBC MANUBANK' differs from the published 'SMBC MANUBANK Marco Island 515 South Figueroa Street Los Angeles, CA 90071 MARCO ISLAND, FL, 34145'

---

## 118. Host International, Inc. 1 Jeff Fuqua Blvd ORLANDO, FL, 32827 (FL)

`warn-fl-2026-01-16-host-international` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-01-16**, effective 2026-01-30..2026-01-30
- **92** affected across 1 published row(s)
  - Host International, Inc. 1 Jeff Fuqua Blvd ORLANDO, FL, 32827 — 92 — no location published — `year=2026 page=2 row 82`
- source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026&page=2>
- the rule's match window: 2025-12-17 .. 2027-02-20

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136261` — event `109096` — tier `exact`

- stored name: `Host International, Inc.`
- stored count **92**, date `2026-01-30`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Host International, Inc.` — 92 — 2026-01-30 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Host International, Inc.' differs from the published 'Host International, Inc. 1 Jeff Fuqua Blvd ORLANDO, FL, 32827'

---

## 119. Saks & Company LLC 2784 Executive Way MIRAMAR, FL, 33025 (FL)

`warn-fl-2026-01-23-saks` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-01-23**, effective 2026-03-27..2026-03-27
- **74** affected across 1 published row(s)
  - Saks & Company LLC 2784 Executive Way MIRAMAR, FL, 33025 — 74 — no location published — `year=2026 page=2 row 79`
- source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026&page=2>
- the rule's match window: 2025-12-24 .. 2027-02-27

**2 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135803` — event `108638` — tier `exact`

- stored name: `Saks & Company LLC`
- stored count **74**, date `2026-03-27`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Saks & Company LLC` — 74 — 2026-03-27 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Saks & Company LLC' differs from the published 'Saks & Company LLC 2784 Executive Way MIRAMAR, FL, 33025'

### row `135291` — event `108126` — tier `loose`

- stored name: `Saks & Company LLC`
- stored count **66**, date `2026-05-01`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Saks & Company LLC` — 66 — 2026-05-01 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count 66 matches neither a component row nor the notice total 74
  - row date is 98 day(s) after the notice date
  - stored name 'Saks & Company LLC' differs from the published 'Saks & Company LLC 2784 Executive Way MIRAMAR, FL, 33025'

---

## 120. Liberty Dental Plan Corporation 3109 W. Dr. Martin Luther King Jr. Blvd Suite 100 TAMPA, FL, 33607 (FL)

`warn-fl-2026-02-05-liberty-dental-plan` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-02-05**, effective 2026-04-06..2026-04-06
- **102** affected across 1 published row(s)
  - Liberty Dental Plan Corporation 3109 W. Dr. Martin Luther King Jr. Blvd Suite 100 TAMPA, FL, 33607 — 102 — no location published — `year=2026 page=2 row 50`
- source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026&page=2>
- the rule's match window: 2026-01-06 .. 2027-03-12

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135638` — event `108473` — tier `exact`

- stored name: `Liberty Dental Plan Corporation`
- stored count **102**, date `2026-04-06`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Liberty Dental Plan Corporation` — 102 — 2026-04-06 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Liberty Dental Plan Corporation' differs from the published 'Liberty Dental Plan Corporation 3109 W. Dr. Martin Luther King Jr. Blvd Suite 100 TAMPA, FL, 33607'

---

## 121. TTEC 7195 34th Street South, SAINT PETERSBURG, FL, 33711 (FL)

`warn-fl-2026-02-13-ttec` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-02-13**, effective 2026-04-14..2026-04-14
- **57** affected across 1 published row(s)
  - TTEC 7195 34th Street South, SAINT PETERSBURG, FL, 33711 — 57 — no location published — `year=2026 page=2 row 45`
- source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026&page=2>
- the rule's match window: 2026-01-14 .. 2027-03-20

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135555` — event `108390` — tier `exact`

- stored name: `TTEC`
- stored count **57**, date `2026-04-14`, state `FL`, source `warn` / `FL WARN notice`
- live now: `TTEC` — 57 — 2026-04-14 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'TTEC' differs from the published 'TTEC 7195 34th Street South, SAINT PETERSBURG, FL, 33711'

---

## 122. Parsec, LLC 6098 Soutel Drive JACKSONVILLE, FL, 32219 (FL)

`warn-fl-2026-02-23-parsec` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-02-23**, effective 2026-05-01..2026-05-01
- **147** affected across 1 published row(s)
  - Parsec, LLC 6098 Soutel Drive JACKSONVILLE, FL, 32219 — 147 — no location published — `year=2026 page=2 row 37`
- source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026&page=2>
- the rule's match window: 2026-01-24 .. 2027-03-30

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135288` — event `108123` — tier `exact`

- stored name: `Parsec, LLC`
- stored count **147**, date `2026-05-01`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Parsec, LLC` — 147 — 2026-05-01 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Parsec, LLC' differs from the published 'Parsec, LLC 6098 Soutel Drive JACKSONVILLE, FL, 32219'

---

## 123. Trulieve, Inc. 13773 Icot Blvd Bldg. 5 CLEAR WATER, FL, 33760 (FL)

`warn-fl-2026-03-02-trulieve` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-03-02**, effective 2026-05-01..2026-05-01
- **58** affected across 1 published row(s)
  - Trulieve, Inc. 13773 Icot Blvd Bldg. 5 CLEAR WATER, FL, 33760 — 58 — no location published — `year=2026 page=2 row 31`
- source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026&page=2>
- the rule's match window: 2026-01-31 .. 2027-04-06

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135290` — event `108125` — tier `exact`

- stored name: `Trulieve, Inc.`
- stored count **58**, date `2026-05-01`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Trulieve, Inc.` — 58 — 2026-05-01 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Trulieve, Inc.' differs from the published 'Trulieve, Inc. 13773 Icot Blvd Bldg. 5 CLEAR WATER, FL, 33760'

---

## 124. HCL America, Inc 9002 San Marco Court ORLANDO, FL, 32819 (FL)

`warn-fl-2026-03-27-hcl-america` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-03-27**, effective 2026-05-26..2026-05-26
- **120** affected across 1 published row(s)
  - HCL America, Inc 9002 San Marco Court ORLANDO, FL, 32819 — 120 — no location published — `year=2026 page=2 row 8`
- source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026&page=2>
- the rule's match window: 2026-02-25 .. 2027-05-01

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135073` — event `107908` — tier `exact`

- stored name: `HCL America, Inc`
- stored count **120**, date `2026-05-26`, state `FL`, source `warn` / `FL WARN notice`
- live now: `HCL America, Inc` — 120 — 2026-05-26 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'HCL America, Inc' differs from the published 'HCL America, Inc 9002 San Marco Court ORLANDO, FL, 32819'

---

## 125. Amazon 27505 SW 132 Ave TMB8 HOMESTEAD, FL, 33032 (FL)

`warn-fl-2026-04-17-amazon` — currently `not_matched`, stratum `primary`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-04-17**, effective 2026-07-02..2026-07-02
- **616** affected across 1 published row(s)
  - Amazon 27505 SW 132 Ave TMB8 HOMESTEAD, FL, 33032 — 616 — no location published — `year=2026 page=2 row 3`
- source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026&page=2>
- the rule's match window: 2026-03-18 .. 2027-05-22

**3 candidate row(s).** Each block below is one row and says nothing about any other.

### row `134509` — event `107344` — tier `exact`

- stored name: `Amazon`
- stored count **616**, date `2026-07-02`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Amazon` — 616 — 2026-07-02 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Amazon' differs from the published 'Amazon 27505 SW 132 Ave TMB8 HOMESTEAD, FL, 33032'

### row `133994` — event `106829` — tier `loose`

- stored name: `Amazon`
- stored count **494**, date `2026-09-17`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Amazon` — 494 — 2026-09-17 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count 494 matches neither a component row nor the notice total 616
  - row date is 153 day(s) after the notice date
  - stored name 'Amazon' differs from the published 'Amazon 27505 SW 132 Ave TMB8 HOMESTEAD, FL, 33032'

### row `176659` — event `149392` — tier `loose`

- stored name: `Amazon`
- stored count **1100**, date `2026-07-27`, state `FL`, source `news` / `San Francisco Chronicle`
- live now: `Amazon` — 1100 — 2026-07-27 — `news`
- our cited source: <https://news.google.com/rss/articles/CBMingFBVV95cUxQR2lKeHp5Ml9teUg5QlVGbWJHTHB5djNrdmJRTmd1Z0pBZjBXd2tUVTZsN3lvRG1lNDRRaFktQXhWczNDTmZ2QWJ3TmJjbHFJX052b0tubTZVcGY4YnFLa3VYTDQ1bjhKeUhMMDJWc0E3Nm81ZlM5RXBsT0dlVDJHc1BZYUUzNjJqdFZwcWI0SkZtVFFSN2pKaXBoZ3MtQQ?oc=5>
- flags for this row:
  - row source is news/filing, not a WARN-tier row
  - job_count 1100 matches neither a component row nor the notice total 616
  - row date is 101 day(s) after the notice date
  - stored name 'Amazon' differs from the published 'Amazon 27505 SW 132 Ave TMB8 HOMESTEAD, FL, 33032'

---

## 126. Republic National Distributing Company 441 SW 12 Ave DEERFIELD BEACH, FL, 33442 (FL)

`warn-fl-2026-04-22-republic-national-distributing` — currently `not_matched`, stratum `large_census`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-04-22**, effective 2026-06-21..2026-06-21
- **653** affected across 3 published row(s)
  - Republic National Distributing Company 441 SW 12 Ave DEERFIELD BEACH, FL, 33442 — 363 — no location published — `year=2026 page=1 row 98`
  - Republic National Distributing Company 9423 North Main Street JACKSONVILLE, FL, 32218 — 169 — no location published — `year=2026 page=1 row 99`
  - Republic National Distributing Company 6256 North W Street PENSACOLA, FL, 32305 — 121 — no location published — `year=2026 page=1 row 100`
- source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026&page=1>
- the rule's match window: 2026-03-23 .. 2027-05-27

**4 candidate row(s).** Each block below is one row and says nothing about any other.

### row `134752` — event `107587` — tier `exact`

- stored name: `Republic National Distributing Company`
- stored count **121**, date `2026-06-21`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Republic National Distributing Company` — 121 — 2026-06-21 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Republic National Distributing Company' differs from the published 'Republic National Distributing Company 441 SW 12 Ave DEERFIELD BEACH, FL, 33442'

### row `134751` — event `107586` — tier `exact`

- stored name: `Republic National Distributing Company`
- stored count **169**, date `2026-06-21`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Republic National Distributing Company` — 169 — 2026-06-21 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Republic National Distributing Company' differs from the published 'Republic National Distributing Company 441 SW 12 Ave DEERFIELD BEACH, FL, 33442'

### row `134750` — event `107585` — tier `exact`

- stored name: `Republic National Distributing Company`
- stored count **363**, date `2026-06-21`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Republic National Distributing Company` — 363 — 2026-06-21 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Republic National Distributing Company' differs from the published 'Republic National Distributing Company 441 SW 12 Ave DEERFIELD BEACH, FL, 33442'

### row `134753` — event `107588` — tier `loose`

- stored name: `Republic National Distributing Company`
- stored count **393**, date `2026-06-21`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Republic National Distributing Company` — 393 — 2026-06-21 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count 393 matches neither a component row nor the notice total 653
  - row date equals this notice's earliest published effective date
  - stored name 'Republic National Distributing Company' differs from the published 'Republic National Distributing Company 441 SW 12 Ave DEERFIELD BEACH, FL, 33442'

---

## 127. Msgr. Bryan Walsh Children’s Village 9525 Sterling Drive MIAMI, FL, 33157 (FL)

`warn-fl-2026-04-27-msgr-bryan-walsh-children` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-04-27**, effective 2026-05-31..2026-05-31
- **84** affected across 1 published row(s)
  - Msgr. Bryan Walsh Children’s Village 9525 Sterling Drive MIAMI, FL, 33157 — 84 — no location published — `year=2026 page=1 row 97`
- source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026&page=1>
- the rule's match window: 2026-03-28 .. 2027-06-01

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135002` — event `107837` — tier `exact`

- stored name: `Msgr. Bryan Walsh Children?s Village`
- stored count **84**, date `2026-05-31`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Msgr. Bryan Walsh Children?s Village` — 84 — 2026-05-31 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Msgr. Bryan Walsh Children?s Village' differs from the published 'Msgr. Bryan Walsh Children’s Village 9525 Sterling Drive MIAMI, FL, 33157'

---

## 128. Spirit Airlines Miami International Airport (MIA) 2100 NW 42nd Ave, Miami MIAMI, FL, 33142 (FL)

`warn-fl-2026-05-04-spirit-airlines-miami-international` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-05-04**, effective 2026-05-02..2026-05-02
- **181** affected across 1 published row(s)
  - Spirit Airlines Miami International Airport (MIA) 2100 NW 42nd Ave, Miami MIAMI, FL, 33142 — 181 — no location published — `year=2026 page=1 row 90`
- source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026&page=1>
- the rule's match window: 2026-04-04 .. 2027-06-08

**5 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135256` — event `108091` — tier `exact`

- stored name: `Spirit Airlines`
- stored count **181**, date `2026-05-02`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Spirit Airlines` — 181 — 2026-05-02 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Miami International Airport (MIA) 2100 NW 42nd Ave, Miami MIAMI, FL, 33142'

### row `135257` — event `108092` — tier `loose`

- stored name: `Spirit Airlines`
- stored count **551**, date `2026-05-02`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Spirit Airlines` — 551 — 2026-05-02 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count 551 matches neither a component row nor the notice total 181
  - row date equals this notice's earliest published effective date
  - stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Miami International Airport (MIA) 2100 NW 42nd Ave, Miami MIAMI, FL, 33142'

### row `135255` — event `108090` — tier `loose`

- stored name: `Spirit Airlines`
- stored count **796**, date `2026-05-02`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Spirit Airlines` — 796 — 2026-05-02 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count 796 matches neither a component row nor the notice total 181
  - row date equals this notice's earliest published effective date
  - stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Miami International Airport (MIA) 2100 NW 42nd Ave, Miami MIAMI, FL, 33142'

### row `135254` — event `108089` — tier `loose`

- stored name: `Spirit Airlines`
- stored count **2529**, date `2026-05-02`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Spirit Airlines` — 2529 — 2026-05-02 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count 2529 matches neither a component row nor the notice total 181
  - row date equals this notice's earliest published effective date
  - stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Miami International Airport (MIA) 2100 NW 42nd Ave, Miami MIAMI, FL, 33142'

### row `176452` — event `149196` — tier `loose`

- stored name: `Spirit Airlines`
- stored count **4000**, date `2026-05-05`, state `FL`, source `news` / `NBC 6 South Florida`
- live now: `Spirit Airlines` — 4000 — 2026-05-05 — `news`
- our cited source: <https://news.google.com/rss/articles/CBMiwwFBVV95cUxQMFM4YWZsUl96aTJiX2FLQldmUlVZbUo5U1dNakxBazAwRC1zZ0RwaXZDVFRKVmU0MlhfOWlxRnhPLVd2b2dWaWtRT0tMSFJzSnJWMDBEUUxIRlpNWlVaOEUxZWN3SlpQdHFnZjcxdlliNjA0eTUxQ1dqakVpRVZYOUVxdms3Z0hWRXhwZy1YWkxUb0ExZ0VJeXJDWW9xTVJqRThpTkVvS1k4YWt5SjZTampva3RsTTd0WmtJRGRLb0pUY2vSAcsBQVVfeXFMTjRLc3ZQdU1XdWZoZmJHb3pENEphMDdyc19XVlR5LU5fdnl6NkQwLUJyT1hYZm9FbVluX0k1azdDWG1LTk1aZjlWVHpBMk9Kbmp3cEEwbkZLRUdxVUtJa09nWW5tTENIOGxCR2dIWFBjaUVDaDNEVmRoRDlnTnJUWUpDajlZeTIzaS01by1GaFFLTUlCVHQ2WWFnZDhPMVQ3UlVxSkF6cXJmeHpZNGpRdHhldDdMUWlpUlhNZ0VlNGtzNlI4WGVvdnNuLTQ?oc=5>
- flags for this row:
  - row source is news/filing, not a WARN-tier row
  - job_count 4000 matches neither a component row nor the notice total 181
  - row date is 1 day(s) after the notice date
  - stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Miami International Airport (MIA) 2100 NW 42nd Ave, Miami MIAMI, FL, 33142'

---

## 129. Spirit Airlines Fort Lauderdale-Hollywood International Airport (FLL) 100 Terminal Dr, Fort Lauderdale FORT LAUDERDALE, FL, 33315 (FL)

`warn-fl-2026-05-04-spirit-airlines-fort-lauderdale` — currently `not_matched`, stratum `large_census`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-05-04**, effective 2026-05-02..2026-05-02
- **2,529** affected across 1 published row(s)
  - Spirit Airlines Fort Lauderdale-Hollywood International Airport (FLL) 100 Terminal Dr, Fort Lauderdale FORT LAUDERDALE, FL, 33315 — 2529 — no location published — `year=2026 page=1 row 88`
- source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026&page=1>
- the rule's match window: 2026-04-04 .. 2027-06-08

**5 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135254` — event `108089` — tier `exact`

- stored name: `Spirit Airlines`
- stored count **2529**, date `2026-05-02`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Spirit Airlines` — 2529 — 2026-05-02 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Fort Lauderdale-Hollywood International Airport (FLL) 100 Terminal Dr, Fort Lauderdale FORT LAUDERDALE, FL, 33315'

### row `135257` — event `108092` — tier `loose`

- stored name: `Spirit Airlines`
- stored count **551**, date `2026-05-02`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Spirit Airlines` — 551 — 2026-05-02 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count 551 matches neither a component row nor the notice total 2529
  - row date equals this notice's earliest published effective date
  - stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Fort Lauderdale-Hollywood International Airport (FLL) 100 Terminal Dr, Fort Lauderdale FORT LAUDERDALE, FL, 33315'

### row `135256` — event `108091` — tier `loose`

- stored name: `Spirit Airlines`
- stored count **181**, date `2026-05-02`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Spirit Airlines` — 181 — 2026-05-02 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count 181 matches neither a component row nor the notice total 2529
  - row date equals this notice's earliest published effective date
  - stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Fort Lauderdale-Hollywood International Airport (FLL) 100 Terminal Dr, Fort Lauderdale FORT LAUDERDALE, FL, 33315'

### row `135255` — event `108090` — tier `loose`

- stored name: `Spirit Airlines`
- stored count **796**, date `2026-05-02`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Spirit Airlines` — 796 — 2026-05-02 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count 796 matches neither a component row nor the notice total 2529
  - row date equals this notice's earliest published effective date
  - stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Fort Lauderdale-Hollywood International Airport (FLL) 100 Terminal Dr, Fort Lauderdale FORT LAUDERDALE, FL, 33315'

### row `176452` — event `149196` — tier `loose`

- stored name: `Spirit Airlines`
- stored count **4000**, date `2026-05-05`, state `FL`, source `news` / `NBC 6 South Florida`
- live now: `Spirit Airlines` — 4000 — 2026-05-05 — `news`
- our cited source: <https://news.google.com/rss/articles/CBMiwwFBVV95cUxQMFM4YWZsUl96aTJiX2FLQldmUlVZbUo5U1dNakxBazAwRC1zZ0RwaXZDVFRKVmU0MlhfOWlxRnhPLVd2b2dWaWtRT0tMSFJzSnJWMDBEUUxIRlpNWlVaOEUxZWN3SlpQdHFnZjcxdlliNjA0eTUxQ1dqakVpRVZYOUVxdms3Z0hWRXhwZy1YWkxUb0ExZ0VJeXJDWW9xTVJqRThpTkVvS1k4YWt5SjZTampva3RsTTd0WmtJRGRLb0pUY2vSAcsBQVVfeXFMTjRLc3ZQdU1XdWZoZmJHb3pENEphMDdyc19XVlR5LU5fdnl6NkQwLUJyT1hYZm9FbVluX0k1azdDWG1LTk1aZjlWVHpBMk9Kbmp3cEEwbkZLRUdxVUtJa09nWW5tTENIOGxCR2dIWFBjaUVDaDNEVmRoRDlnTnJUWUpDajlZeTIzaS01by1GaFFLTUlCVHQ2WWFnZDhPMVQ3UlVxSkF6cXJmeHpZNGpRdHhldDdMUWlpUlhNZ0VlNGtzNlI4WGVvdnNuLTQ?oc=5>
- flags for this row:
  - row source is news/filing, not a WARN-tier row
  - job_count 4000 matches neither a component row nor the notice total 2529
  - row date is 1 day(s) after the notice date
  - stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Fort Lauderdale-Hollywood International Airport (FLL) 100 Terminal Dr, Fort Lauderdale FORT LAUDERDALE, FL, 33315'

---

## 130. Spirit Airlines MCO Infight & Operations Center (OOC) 10084 Air Tran Blvd Orlando ORLANDO, FL, 32827 (FL)

`warn-fl-2026-05-04-spirit-airlines-mco-infight` — currently `not_matched`, stratum `large_census`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-05-04**, effective 2026-05-02..2026-05-02
- **796** affected across 1 published row(s)
  - Spirit Airlines MCO Infight & Operations Center (OOC) 10084 Air Tran Blvd Orlando ORLANDO, FL, 32827 — 796 — no location published — `year=2026 page=1 row 91`
- source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026&page=1>
- the rule's match window: 2026-04-04 .. 2027-06-08

**5 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135255` — event `108090` — tier `exact`

- stored name: `Spirit Airlines`
- stored count **796**, date `2026-05-02`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Spirit Airlines` — 796 — 2026-05-02 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Spirit Airlines' differs from the published 'Spirit Airlines MCO Infight & Operations Center (OOC) 10084 Air Tran Blvd Orlando ORLANDO, FL, 32827'

### row `135257` — event `108092` — tier `loose`

- stored name: `Spirit Airlines`
- stored count **551**, date `2026-05-02`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Spirit Airlines` — 551 — 2026-05-02 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count 551 matches neither a component row nor the notice total 796
  - row date equals this notice's earliest published effective date
  - stored name 'Spirit Airlines' differs from the published 'Spirit Airlines MCO Infight & Operations Center (OOC) 10084 Air Tran Blvd Orlando ORLANDO, FL, 32827'

### row `135256` — event `108091` — tier `loose`

- stored name: `Spirit Airlines`
- stored count **181**, date `2026-05-02`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Spirit Airlines` — 181 — 2026-05-02 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count 181 matches neither a component row nor the notice total 796
  - row date equals this notice's earliest published effective date
  - stored name 'Spirit Airlines' differs from the published 'Spirit Airlines MCO Infight & Operations Center (OOC) 10084 Air Tran Blvd Orlando ORLANDO, FL, 32827'

### row `135254` — event `108089` — tier `loose`

- stored name: `Spirit Airlines`
- stored count **2529**, date `2026-05-02`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Spirit Airlines` — 2529 — 2026-05-02 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count 2529 matches neither a component row nor the notice total 796
  - row date equals this notice's earliest published effective date
  - stored name 'Spirit Airlines' differs from the published 'Spirit Airlines MCO Infight & Operations Center (OOC) 10084 Air Tran Blvd Orlando ORLANDO, FL, 32827'

### row `176452` — event `149196` — tier `loose`

- stored name: `Spirit Airlines`
- stored count **4000**, date `2026-05-05`, state `FL`, source `news` / `NBC 6 South Florida`
- live now: `Spirit Airlines` — 4000 — 2026-05-05 — `news`
- our cited source: <https://news.google.com/rss/articles/CBMiwwFBVV95cUxQMFM4YWZsUl96aTJiX2FLQldmUlVZbUo5U1dNakxBazAwRC1zZ0RwaXZDVFRKVmU0MlhfOWlxRnhPLVd2b2dWaWtRT0tMSFJzSnJWMDBEUUxIRlpNWlVaOEUxZWN3SlpQdHFnZjcxdlliNjA0eTUxQ1dqakVpRVZYOUVxdms3Z0hWRXhwZy1YWkxUb0ExZ0VJeXJDWW9xTVJqRThpTkVvS1k4YWt5SjZTampva3RsTTd0WmtJRGRLb0pUY2vSAcsBQVVfeXFMTjRLc3ZQdU1XdWZoZmJHb3pENEphMDdyc19XVlR5LU5fdnl6NkQwLUJyT1hYZm9FbVluX0k1azdDWG1LTk1aZjlWVHpBMk9Kbmp3cEEwbkZLRUdxVUtJa09nWW5tTENIOGxCR2dIWFBjaUVDaDNEVmRoRDlnTnJUWUpDajlZeTIzaS01by1GaFFLTUlCVHQ2WWFnZDhPMVQ3UlVxSkF6cXJmeHpZNGpRdHhldDdMUWlpUlhNZ0VlNGtzNlI4WGVvdnNuLTQ?oc=5>
- flags for this row:
  - row source is news/filing, not a WARN-tier row
  - job_count 4000 matches neither a component row nor the notice total 796
  - row date is 1 day(s) after the notice date
  - stored name 'Spirit Airlines' differs from the published 'Spirit Airlines MCO Infight & Operations Center (OOC) 10084 Air Tran Blvd Orlando ORLANDO, FL, 32827'

---

## 131. Spirit Airlines Orlando International Airport (MCO) 1 Jeff Fuqua Blvd, Orlando ORLANDO, FL, 32827 (FL)

`warn-fl-2026-05-04-spirit-airlines-orlando-international` — currently `not_matched`, stratum `large_census`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-05-04**, effective 2026-05-02..2026-05-02
- **796** affected across 1 published row(s)
  - Spirit Airlines Orlando International Airport (MCO) 1 Jeff Fuqua Blvd, Orlando ORLANDO, FL, 32827 — 796 — no location published — `year=2026 page=1 row 89`
- source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026&page=1>
- the rule's match window: 2026-04-04 .. 2027-06-08

**5 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135255` — event `108090` — tier `exact`

- stored name: `Spirit Airlines`
- stored count **796**, date `2026-05-02`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Spirit Airlines` — 796 — 2026-05-02 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Orlando International Airport (MCO) 1 Jeff Fuqua Blvd, Orlando ORLANDO, FL, 32827'

### row `135257` — event `108092` — tier `loose`

- stored name: `Spirit Airlines`
- stored count **551**, date `2026-05-02`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Spirit Airlines` — 551 — 2026-05-02 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count 551 matches neither a component row nor the notice total 796
  - row date equals this notice's earliest published effective date
  - stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Orlando International Airport (MCO) 1 Jeff Fuqua Blvd, Orlando ORLANDO, FL, 32827'

### row `135256` — event `108091` — tier `loose`

- stored name: `Spirit Airlines`
- stored count **181**, date `2026-05-02`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Spirit Airlines` — 181 — 2026-05-02 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count 181 matches neither a component row nor the notice total 796
  - row date equals this notice's earliest published effective date
  - stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Orlando International Airport (MCO) 1 Jeff Fuqua Blvd, Orlando ORLANDO, FL, 32827'

### row `135254` — event `108089` — tier `loose`

- stored name: `Spirit Airlines`
- stored count **2529**, date `2026-05-02`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Spirit Airlines` — 2529 — 2026-05-02 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count 2529 matches neither a component row nor the notice total 796
  - row date equals this notice's earliest published effective date
  - stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Orlando International Airport (MCO) 1 Jeff Fuqua Blvd, Orlando ORLANDO, FL, 32827'

### row `176452` — event `149196` — tier `loose`

- stored name: `Spirit Airlines`
- stored count **4000**, date `2026-05-05`, state `FL`, source `news` / `NBC 6 South Florida`
- live now: `Spirit Airlines` — 4000 — 2026-05-05 — `news`
- our cited source: <https://news.google.com/rss/articles/CBMiwwFBVV95cUxQMFM4YWZsUl96aTJiX2FLQldmUlVZbUo5U1dNakxBazAwRC1zZ0RwaXZDVFRKVmU0MlhfOWlxRnhPLVd2b2dWaWtRT0tMSFJzSnJWMDBEUUxIRlpNWlVaOEUxZWN3SlpQdHFnZjcxdlliNjA0eTUxQ1dqakVpRVZYOUVxdms3Z0hWRXhwZy1YWkxUb0ExZ0VJeXJDWW9xTVJqRThpTkVvS1k4YWt5SjZTampva3RsTTd0WmtJRGRLb0pUY2vSAcsBQVVfeXFMTjRLc3ZQdU1XdWZoZmJHb3pENEphMDdyc19XVlR5LU5fdnl6NkQwLUJyT1hYZm9FbVluX0k1azdDWG1LTk1aZjlWVHpBMk9Kbmp3cEEwbkZLRUdxVUtJa09nWW5tTENIOGxCR2dIWFBjaUVDaDNEVmRoRDlnTnJUWUpDajlZeTIzaS01by1GaFFLTUlCVHQ2WWFnZDhPMVQ3UlVxSkF6cXJmeHpZNGpRdHhldDdMUWlpUlhNZ0VlNGtzNlI4WGVvdnNuLTQ?oc=5>
- flags for this row:
  - row source is news/filing, not a WARN-tier row
  - job_count 4000 matches neither a component row nor the notice total 796
  - row date is 1 day(s) after the notice date
  - stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Orlando International Airport (MCO) 1 Jeff Fuqua Blvd, Orlando ORLANDO, FL, 32827'

---

## 132. Spirit Airlines Spirit Support Center 1731 Radiant Drive Dania Beach DANIA BEACH, FL, 33004 (FL)

`warn-fl-2026-05-04-spirit-airlines-spirit-support` — currently `not_matched`, stratum `large_census`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-05-04**, effective 2026-05-02..2026-05-02
- **551** affected across 1 published row(s)
  - Spirit Airlines Spirit Support Center 1731 Radiant Drive Dania Beach DANIA BEACH, FL, 33004 — 551 — no location published — `year=2026 page=1 row 92`
- source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026&page=1>
- the rule's match window: 2026-04-04 .. 2027-06-08

**5 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135257` — event `108092` — tier `exact`

- stored name: `Spirit Airlines`
- stored count **551**, date `2026-05-02`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Spirit Airlines` — 551 — 2026-05-02 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count equals one published component row of this notice
  - row date equals this notice's earliest published effective date
  - stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Spirit Support Center 1731 Radiant Drive Dania Beach DANIA BEACH, FL, 33004'

### row `135256` — event `108091` — tier `loose`

- stored name: `Spirit Airlines`
- stored count **181**, date `2026-05-02`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Spirit Airlines` — 181 — 2026-05-02 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count 181 matches neither a component row nor the notice total 551
  - row date equals this notice's earliest published effective date
  - stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Spirit Support Center 1731 Radiant Drive Dania Beach DANIA BEACH, FL, 33004'

### row `135255` — event `108090` — tier `loose`

- stored name: `Spirit Airlines`
- stored count **796**, date `2026-05-02`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Spirit Airlines` — 796 — 2026-05-02 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count 796 matches neither a component row nor the notice total 551
  - row date equals this notice's earliest published effective date
  - stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Spirit Support Center 1731 Radiant Drive Dania Beach DANIA BEACH, FL, 33004'

### row `135254` — event `108089` — tier `loose`

- stored name: `Spirit Airlines`
- stored count **2529**, date `2026-05-02`, state `FL`, source `warn` / `FL WARN notice`
- live now: `Spirit Airlines` — 2529 — 2026-05-02 — `warn`
- our cited source: <https://reactwarn.floridajobs.org/WarnList/Records?year=2026>
- flags for this row:
  - job_count 2529 matches neither a component row nor the notice total 551
  - row date equals this notice's earliest published effective date
  - stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Spirit Support Center 1731 Radiant Drive Dania Beach DANIA BEACH, FL, 33004'

### row `176452` — event `149196` — tier `loose`

- stored name: `Spirit Airlines`
- stored count **4000**, date `2026-05-05`, state `FL`, source `news` / `NBC 6 South Florida`
- live now: `Spirit Airlines` — 4000 — 2026-05-05 — `news`
- our cited source: <https://news.google.com/rss/articles/CBMiwwFBVV95cUxQMFM4YWZsUl96aTJiX2FLQldmUlVZbUo5U1dNakxBazAwRC1zZ0RwaXZDVFRKVmU0MlhfOWlxRnhPLVd2b2dWaWtRT0tMSFJzSnJWMDBEUUxIRlpNWlVaOEUxZWN3SlpQdHFnZjcxdlliNjA0eTUxQ1dqakVpRVZYOUVxdms3Z0hWRXhwZy1YWkxUb0ExZ0VJeXJDWW9xTVJqRThpTkVvS1k4YWt5SjZTampva3RsTTd0WmtJRGRLb0pUY2vSAcsBQVVfeXFMTjRLc3ZQdU1XdWZoZmJHb3pENEphMDdyc19XVlR5LU5fdnl6NkQwLUJyT1hYZm9FbVluX0k1azdDWG1LTk1aZjlWVHpBMk9Kbmp3cEEwbkZLRUdxVUtJa09nWW5tTENIOGxCR2dIWFBjaUVDaDNEVmRoRDlnTnJUWUpDajlZeTIzaS01by1GaFFLTUlCVHQ2WWFnZDhPMVQ3UlVxSkF6cXJmeHpZNGpRdHhldDdMUWlpUlhNZ0VlNGtzNlI4WGVvdnNuLTQ?oc=5>
- flags for this row:
  - row source is news/filing, not a WARN-tier row
  - job_count 4000 matches neither a component row nor the notice total 551
  - row date is 1 day(s) after the notice date
  - stored name 'Spirit Airlines' differs from the published 'Spirit Airlines Spirit Support Center 1731 Radiant Drive Dania Beach DANIA BEACH, FL, 33004'

---

