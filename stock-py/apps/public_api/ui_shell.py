from __future__ import annotations

import json
from html import escape
from typing import Literal

SurfaceName = Literal["app", "platform", "admin"]

_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang=\"zh-CN\">
<head>
    <meta charset=\"UTF-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <title>__TITLE__</title>
    <link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">
    <link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin>
    <link href=\"https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=IBM+Plex+Mono:wght@400;500;600&family=Space+Grotesk:wght@400;500;600;700&display=swap\" rel=\"stylesheet\">
    <style>
        :root {
            color-scheme: light;
            --bg: #f3efe5;
            --panel: rgba(255, 252, 247, 0.92);
            --panel-strong: #fffdf8;
            --ink: #182321;
            --muted: #596a67;
            --line: rgba(24, 35, 33, 0.12);
            --accent: #0c7c59;
            --accent-strong: #0a6247;
            --warm: #d99f4f;
            --danger: #a33b2f;
            --shadow: 0 18px 45px rgba(24, 35, 33, 0.08);
            --radius-xl: 28px;
            --radius-lg: 20px;
            --radius-md: 14px;
            --radius-sm: 10px;
        }

        * {
            box-sizing: border-box;
        }

        html {
            min-height: 100%;
            background:
                radial-gradient(circle at top left, rgba(217, 159, 79, 0.28), transparent 28%),
                radial-gradient(circle at top right, rgba(12, 124, 89, 0.18), transparent 32%),
                linear-gradient(180deg, #f8f5ed 0%, var(--bg) 100%);
        }

        body {
            margin: 0;
            min-height: 100dvh;
            color: var(--ink);
            font-family: "Trebuchet MS", "Segoe UI", sans-serif;
        }

        a {
            color: inherit;
        }

        .page-shell {
            max-width: 1320px;
            margin: 0 auto;
            padding: 24px 20px 56px;
        }

        .masthead {
            display: flex;
            justify-content: space-between;
            gap: 16px;
            align-items: center;
            margin-bottom: 20px;
            padding: 24px 28px;
            border-radius: var(--radius-xl);
            background: rgba(255, 253, 248, 0.8);
            border: 1px solid rgba(24, 35, 33, 0.08);
            box-shadow: var(--shadow);
            backdrop-filter: blur(18px);
        }

        .brand-block {
            display: flex;
            gap: 14px;
            align-items: center;
        }

        .brand-mark {
            width: 44px;
            height: 44px;
            border-radius: 14px;
            background: linear-gradient(135deg, var(--accent) 0%, #1d4f91 100%);
            color: #fff;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            letter-spacing: 0.08em;
        }

        .brand-copy h1,
        .panel h2,
        .hero-copy h2 {
            font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Georgia, serif;
        }

        .brand-copy h1 {
            margin: 0;
            font-size: 1.2rem;
        }

        .brand-copy p {
            margin: 4px 0 0;
            color: var(--muted);
            font-size: 0.94rem;
        }

        .nav-row {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }

        .nav-chip {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 10px 14px;
            border-radius: 999px;
            text-decoration: none;
            background: rgba(255, 255, 255, 0.6);
            border: 1px solid rgba(24, 35, 33, 0.08);
            color: var(--muted);
            transition: transform 160ms ease, background 160ms ease, color 160ms ease;
        }

        .nav-chip:hover {
            transform: translateY(-1px);
            color: var(--ink);
        }

        .nav-chip.active {
            background: var(--ink);
            color: #fdfbf7;
            border-color: transparent;
        }

        .hero {
            display: grid;
            grid-template-columns: minmax(0, 1.45fr) minmax(280px, 0.95fr);
            gap: 18px;
            margin-bottom: 18px;
        }

        .hero-card,
        .hero-aside,
        .panel {
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: var(--radius-xl);
            box-shadow: var(--shadow);
            backdrop-filter: blur(18px);
        }

        .hero-card {
            position: relative;
            overflow: hidden;
            padding: 32px;
        }

        .hero-card::after {
            content: "";
            position: absolute;
            inset: auto -10% -28% 44%;
            height: 180px;
            background: radial-gradient(circle, rgba(217, 159, 79, 0.22), transparent 70%);
            pointer-events: none;
        }

        .hero-kicker {
            display: inline-flex;
            padding: 6px 10px;
            border-radius: 999px;
            background: rgba(12, 124, 89, 0.1);
            color: var(--accent-strong);
            font-size: 0.8rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }

        .hero-copy h2 {
            margin: 14px 0 10px;
            font-size: clamp(2rem, 4vw, 3.3rem);
            line-height: 1.02;
        }

        .hero-copy p {
            max-width: 64ch;
            margin: 0;
            color: var(--muted);
            line-height: 1.7;
        }

        .hero-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 12px;
            margin-top: 22px;
        }

        .hero-stat {
            padding: 14px;
            border-radius: var(--radius-md);
            background: rgba(255, 255, 255, 0.6);
            border: 1px solid rgba(24, 35, 33, 0.08);
        }

        .hero-stat strong {
            display: block;
            font-size: 1.15rem;
        }

        .hero-stat span {
            display: block;
            margin-top: 4px;
            color: var(--muted);
            font-size: 0.88rem;
        }

        .hero-aside {
            padding: 26px 24px;
        }

        .hero-aside h3 {
            margin: 0 0 12px;
            font-size: 1rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: var(--muted);
        }

        .hero-aside ul {
            margin: 0;
            padding-left: 18px;
            color: var(--muted);
            line-height: 1.7;
        }

        .surface-grid {
            display: grid;
            grid-template-columns: repeat(12, minmax(0, 1fr));
            gap: 18px;
        }

        .panel {
            padding: 22px;
            grid-column: span 6;
        }

        .panel.wide {
            grid-column: span 12;
        }

        .panel.tall {
            min-height: 100%;
        }

        .panel-header {
            display: flex;
            justify-content: space-between;
            gap: 12px;
            align-items: flex-start;
            margin-bottom: 14px;
        }

        .panel-header h2 {
            margin: 0;
            font-size: 1.45rem;
        }

        .pill {
            display: inline-flex;
            align-items: center;
            padding: 6px 10px;
            border-radius: 999px;
            background: rgba(12, 124, 89, 0.1);
            color: var(--accent-strong);
            font-size: 0.8rem;
        }

        .panel-copy,
        .panel-note,
        .helper {
            color: var(--muted);
            line-height: 1.6;
            font-size: 0.94rem;
        }

        .field-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 12px;
            margin: 14px 0;
        }

        .field-grid.single {
            grid-template-columns: minmax(0, 1fr);
        }

        label {
            display: flex;
            flex-direction: column;
            gap: 6px;
            color: var(--muted);
            font-size: 0.86rem;
        }

        input,
        textarea,
        select {
            width: 100%;
            border: 1px solid rgba(24, 35, 33, 0.12);
            border-radius: var(--radius-sm);
            padding: 12px 14px;
            color: var(--ink);
            background: rgba(255, 255, 255, 0.72);
            font: inherit;
        }

        textarea {
            min-height: 112px;
            resize: vertical;
        }

        .inline-check {
            display: inline-flex;
            align-items: center;
            gap: 10px;
            font-size: 0.92rem;
            color: var(--ink);
        }

        .inline-check input {
            width: auto;
            margin: 0;
        }

        .button-row {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 14px;
        }

        button {
            border: none;
            border-radius: 999px;
            padding: 11px 16px;
            background: var(--accent);
            color: #fff;
            font: inherit;
            cursor: pointer;
            transition: transform 160ms ease, background 160ms ease;
        }

        button:hover {
            transform: translateY(-1px);
            background: var(--accent-strong);
        }

        button.secondary {
            background: rgba(24, 35, 33, 0.08);
            color: var(--ink);
        }

        button.ghost {
            background: transparent;
            color: var(--muted);
            border: 1px solid rgba(24, 35, 33, 0.12);
        }

        .status {
            min-height: 24px;
            margin-top: 12px;
            font-size: 0.92rem;
            color: var(--muted);
        }

        .status[data-tone=\"success\"] {
            color: var(--accent-strong);
        }

        .status[data-tone=\"error\"] {
            color: var(--danger);
        }

        .json-output {
            margin-top: 14px;
            min-height: 180px;
            max-height: 420px;
            overflow: auto;
            padding: 14px;
            border-radius: var(--radius-md);
            background: #f8f4ed;
            border: 1px solid rgba(24, 35, 33, 0.08);
            color: #203533;
            font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
            font-size: 0.85rem;
            line-height: 1.6;
            white-space: pre-wrap;
            word-break: break-word;
        }

        .table-wrap {
            margin-top: 14px;
            overflow: auto;
            border-radius: var(--radius-md);
            border: 1px solid rgba(24, 35, 33, 0.08);
            background: rgba(255, 255, 255, 0.7);
        }

        table {
            width: 100%;
            border-collapse: collapse;
            min-width: 540px;
        }

        th,
        td {
            padding: 12px 14px;
            border-bottom: 1px solid rgba(24, 35, 33, 0.08);
            text-align: left;
            font-size: 0.92rem;
            vertical-align: top;
        }

        th {
            background: rgba(24, 35, 33, 0.04);
            color: var(--muted);
            font-weight: 600;
        }

        .empty-state {
            padding: 18px;
            color: var(--muted);
        }

        .token-note {
            margin-top: 10px;
            color: var(--muted);
            font-size: 0.9rem;
        }

        @media (max-width: 1100px) {
            .hero {
                grid-template-columns: minmax(0, 1fr);
            }

            .panel {
                grid-column: span 12;
            }
        }

        @media (max-width: 720px) {
            .page-shell {
                padding: 16px 14px 34px;
            }

            .masthead {
                flex-direction: column;
                align-items: stretch;
            }

            .hero-card,
            .hero-aside,
            .panel {
                padding: 18px;
            }

            .field-grid,
            .hero-grid {
                grid-template-columns: minmax(0, 1fr);
            }

            .nav-row,
            .button-row {
                flex-direction: column;
            }

            .nav-chip,
            button {
                justify-content: center;
            }
        }

        :root {
            --bg: #f6f1e8;
            --panel: rgba(255, 252, 247, 0.84);
            --panel-strong: rgba(255, 255, 255, 0.94);
            --ink: #182623;
            --muted: #62716d;
            --line: rgba(24, 38, 35, 0.12);
            --line-strong: rgba(24, 38, 35, 0.22);
            --accent: #0f7a68;
            --accent-strong: #0a5f52;
            --accent-soft: rgba(15, 122, 104, 0.14);
            --warm: #cc8e47;
            --danger: #a4463b;
            --danger-soft: rgba(164, 70, 59, 0.12);
            --success-soft: rgba(15, 122, 104, 0.12);
            --shadow: 0 26px 60px rgba(24, 38, 35, 0.10);
            --shadow-soft: 0 14px 30px rgba(24, 38, 35, 0.07);
            --radius-xl: 30px;
            --radius-lg: 24px;
            --radius-md: 18px;
            --radius-sm: 14px;
        }

        body[data-surface="platform"] {
            --accent: #1f6ea9;
            --accent-strong: #174f7b;
            --accent-soft: rgba(31, 110, 169, 0.14);
            --warm: #d4a14e;
        }

        body[data-surface="admin"] {
            --accent: #b15d40;
            --accent-strong: #8e4630;
            --accent-soft: rgba(177, 93, 64, 0.14);
            --warm: #b7833a;
        }

        html {
            scroll-behavior: smooth;
            background:
                radial-gradient(circle at top left, rgba(15, 122, 104, 0.12), transparent 28%),
                radial-gradient(circle at top right, rgba(204, 142, 71, 0.16), transparent 32%),
                linear-gradient(180deg, #fcfaf5 0%, var(--bg) 100%);
        }

        body {
            position: relative;
            overflow-x: hidden;
            font-family: "Space Grotesk", "Segoe UI", sans-serif;
            color: var(--ink);
        }

        body::before {
            content: "";
            position: fixed;
            inset: 0;
            pointer-events: none;
            background:
                radial-gradient(circle at 12% 14%, color-mix(in srgb, var(--accent) 16%, transparent), transparent 24%),
                radial-gradient(circle at 88% 10%, rgba(204, 142, 71, 0.18), transparent 20%),
                radial-gradient(circle at 82% 78%, color-mix(in srgb, var(--accent) 10%, white), transparent 24%);
            opacity: 0.9;
        }

        body::after {
            content: "";
            position: fixed;
            inset: 0;
            pointer-events: none;
            background-image:
                linear-gradient(rgba(24, 38, 35, 0.028) 1px, transparent 1px),
                linear-gradient(90deg, rgba(24, 38, 35, 0.028) 1px, transparent 1px);
            background-size: 28px 28px;
            mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.5), transparent 88%);
        }

        .page-shell {
            position: relative;
            z-index: 1;
            max-width: 1380px;
            padding: 24px 24px 64px;
        }

        .masthead {
            position: sticky;
            top: 18px;
            z-index: 20;
            margin-bottom: 24px;
            padding: 18px 20px;
            border-radius: 26px;
            background: rgba(255, 252, 247, 0.68);
            border: 1px solid rgba(255, 255, 255, 0.45);
            box-shadow: var(--shadow-soft);
            backdrop-filter: blur(20px) saturate(1.08);
        }

        .brand-mark {
            width: 52px;
            height: 52px;
            border-radius: 18px;
            background:
                linear-gradient(145deg, var(--accent) 0%, var(--accent-strong) 60%, rgba(20, 34, 31, 0.96) 100%);
            box-shadow:
                inset 0 1px 0 rgba(255, 255, 255, 0.24),
                0 14px 32px color-mix(in srgb, var(--accent) 28%, transparent);
            font-family: "IBM Plex Mono", monospace;
            font-size: 1rem;
        }

        .brand-copy h1,
        .panel h2,
        .hero-copy h2,
        .hero-aside h3,
        .panel h3 {
            font-family: "Fraunces", Georgia, serif;
        }

        .brand-copy h1 {
            font-size: 1.45rem;
            letter-spacing: -0.04em;
            line-height: 1;
        }

        .brand-copy p {
            margin-top: 6px;
            max-width: 34rem;
            color: var(--muted);
        }

        .nav-row {
            gap: 12px;
            justify-content: flex-end;
        }

        .nav-chip {
            min-height: 42px;
            padding: 10px 16px;
            border-radius: 999px;
            font-size: 0.92rem;
            font-weight: 600;
            background: rgba(255, 255, 255, 0.62);
            border: 1px solid rgba(24, 38, 35, 0.08);
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.42);
        }

        .nav-chip:hover {
            background: rgba(255, 255, 255, 0.94);
            box-shadow: 0 12px 24px rgba(24, 38, 35, 0.08);
        }

        .nav-chip.active {
            background: linear-gradient(135deg, var(--ink) 0%, rgba(24, 38, 35, 0.92) 100%);
            color: #fffaf2;
            box-shadow: 0 16px 30px rgba(24, 38, 35, 0.16);
        }

        .hero {
            gap: 20px;
            margin-bottom: 22px;
            align-items: stretch;
        }

        .hero-card,
        .hero-aside,
        .panel {
            border: 1px solid rgba(255, 255, 255, 0.42);
            border-radius: var(--radius-xl);
            background:
                linear-gradient(180deg, rgba(255, 255, 255, 0.90) 0%, rgba(255, 252, 247, 0.70) 100%);
            box-shadow: var(--shadow);
            backdrop-filter: blur(20px) saturate(1.04);
        }

        .hero-card {
            min-height: 330px;
            padding: 34px;
        }

        .hero-card::before {
            content: "";
            position: absolute;
            inset: 0 0 auto 0;
            height: 4px;
            background: linear-gradient(90deg, var(--accent), rgba(255, 255, 255, 0));
        }

        .hero-card::after {
            inset: auto -12% -30% 40%;
            height: 240px;
            background:
                radial-gradient(circle, color-mix(in srgb, var(--accent) 16%, transparent), transparent 66%),
                radial-gradient(circle at 68% 40%, rgba(204, 142, 71, 0.18), transparent 50%);
        }

        .hero-kicker {
            padding: 8px 12px;
            border: 1px solid rgba(15, 122, 104, 0.14);
            background: var(--accent-soft);
            color: var(--accent-strong);
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.12em;
        }

        .hero-copy h2 {
            margin: 18px 0 12px;
            font-size: clamp(2.4rem, 5vw, 4.4rem);
            letter-spacing: -0.05em;
            line-height: 0.96;
            max-width: 11ch;
        }

        .hero-copy p {
            max-width: 62ch;
            color: var(--muted);
            font-size: 1rem;
        }

        .hero-grid {
            gap: 14px;
            margin-top: 26px;
        }

        .hero-stat {
            position: relative;
            overflow: hidden;
            padding: 16px 16px 18px;
            border-radius: 18px;
            background: linear-gradient(180deg, rgba(255, 255, 255, 0.82) 0%, rgba(248, 243, 235, 0.88) 100%);
            border: 1px solid rgba(24, 38, 35, 0.08);
        }

        .hero-stat::before {
            content: "";
            position: absolute;
            inset: 0 0 auto 0;
            height: 3px;
            background: linear-gradient(90deg, var(--accent), rgba(255, 255, 255, 0));
            opacity: 0.8;
        }

        .hero-stat strong {
            font-family: "IBM Plex Mono", monospace;
            font-size: 1.02rem;
            letter-spacing: -0.02em;
        }

        .hero-stat span {
            margin-top: 8px;
            line-height: 1.55;
        }

        .hero-aside {
            padding: 28px 24px;
            position: relative;
            overflow: hidden;
        }

        .hero-aside::before {
            content: "";
            position: absolute;
            inset: 0 0 auto 0;
            height: 3px;
            background: linear-gradient(90deg, rgba(204, 142, 71, 0.8), rgba(255, 255, 255, 0));
        }

        .hero-aside h3 {
            margin-bottom: 14px;
            font-size: 1.18rem;
            letter-spacing: -0.03em;
            text-transform: none;
            color: var(--ink);
        }

        .hero-aside ul {
            padding-left: 20px;
            line-height: 1.75;
        }

        .hero-aside li + li {
            margin-top: 8px;
        }

        .surface-grid {
            gap: 20px;
            align-items: start;
        }

        .surface-grid > .panel {
            animation: shell-rise 440ms ease both;
        }

        .surface-grid > .panel:nth-child(1) { animation-delay: 30ms; }
        .surface-grid > .panel:nth-child(2) { animation-delay: 80ms; }
        .surface-grid > .panel:nth-child(3) { animation-delay: 130ms; }
        .surface-grid > .panel:nth-child(4) { animation-delay: 180ms; }
        .surface-grid > .panel:nth-child(5) { animation-delay: 230ms; }
        .surface-grid > .panel:nth-child(6) { animation-delay: 280ms; }
        .surface-grid > .panel:nth-child(7) { animation-delay: 330ms; }
        .surface-grid > .panel:nth-child(8) { animation-delay: 380ms; }

        .panel {
            position: relative;
            overflow: hidden;
            padding: 24px;
            border-radius: 28px;
        }

        .panel::before {
            content: "";
            position: absolute;
            inset: 0 0 auto 0;
            height: 4px;
            background: linear-gradient(90deg, var(--accent), rgba(255, 255, 255, 0));
        }

        .panel::after {
            content: "";
            position: absolute;
            inset: auto -10% -28% auto;
            width: 180px;
            height: 180px;
            border-radius: 999px;
            background: radial-gradient(circle, color-mix(in srgb, var(--accent) 8%, transparent), transparent 68%);
            pointer-events: none;
        }

        .panel.wide {
            grid-column: span 12;
        }

        .panel-header {
            margin-bottom: 16px;
            gap: 14px;
            align-items: flex-start;
        }

        .panel-header h2 {
            font-size: 1.58rem;
            letter-spacing: -0.04em;
            line-height: 1.02;
        }

        .pill {
            padding: 7px 12px;
            border: 1px solid rgba(255, 255, 255, 0.5);
            background: var(--accent-soft);
            color: var(--accent-strong);
            font-size: 0.76rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }

        .panel-copy,
        .panel-note,
        .helper,
        .token-note {
            color: var(--muted);
            font-size: 0.95rem;
            line-height: 1.7;
        }

        .panel-note code,
        .panel-copy code,
        .helper code,
        .hero-aside code {
            padding: 2px 6px;
            border-radius: 8px;
            background: rgba(24, 38, 35, 0.06);
            font-family: "IBM Plex Mono", monospace;
            font-size: 0.84em;
        }

        .field-grid {
            gap: 14px;
            margin: 16px 0;
        }

        label {
            gap: 8px;
            color: var(--muted);
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }

        input,
        textarea,
        select {
            border: 1px solid rgba(24, 38, 35, 0.10);
            border-radius: 16px;
            padding: 13px 14px;
            background: rgba(255, 255, 255, 0.74);
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.48);
            color: var(--ink);
            font-family: "Space Grotesk", "Segoe UI", sans-serif;
            transition: border-color 140ms ease, box-shadow 140ms ease, transform 140ms ease;
        }

        textarea {
            min-height: 128px;
        }

        input:focus,
        textarea:focus,
        select:focus {
            outline: none;
            border-color: color-mix(in srgb, var(--accent) 72%, white);
            box-shadow: 0 0 0 4px var(--accent-soft);
            background: rgba(255, 255, 255, 0.96);
        }

        .inline-check {
            gap: 12px;
            padding: 12px 14px;
            border-radius: 16px;
            background: rgba(255, 255, 255, 0.64);
            border: 1px solid rgba(24, 38, 35, 0.08);
        }

        .button-row {
            gap: 12px;
            margin-top: 16px;
        }

        button {
            min-height: 44px;
            padding: 11px 18px;
            border-radius: 999px;
            font-family: "Space Grotesk", "Segoe UI", sans-serif;
            font-size: 0.95rem;
            font-weight: 700;
            letter-spacing: 0.01em;
            background: linear-gradient(135deg, var(--accent) 0%, var(--accent-strong) 100%);
            box-shadow: 0 16px 26px color-mix(in srgb, var(--accent) 26%, transparent);
        }

        button:hover {
            transform: translateY(-1px);
            background: linear-gradient(135deg, color-mix(in srgb, var(--accent) 92%, white), var(--accent-strong));
        }

        button.secondary {
            background: rgba(24, 38, 35, 0.08);
            color: var(--ink);
            border: 1px solid rgba(24, 38, 35, 0.10);
            box-shadow: none;
        }

        button.ghost {
            background: rgba(255, 255, 255, 0.62);
            color: var(--muted);
            border: 1px solid rgba(24, 38, 35, 0.12);
            box-shadow: none;
        }

        .status {
            margin-top: 14px;
            min-height: 0;
            padding: 12px 14px;
            border-radius: 16px;
            background: rgba(24, 38, 35, 0.05);
            border: 1px solid rgba(24, 38, 35, 0.08);
            color: var(--muted);
            font-size: 0.92rem;
        }

        .status[data-tone="success"] {
            background: var(--success-soft);
            border-color: rgba(15, 122, 104, 0.16);
            color: var(--accent-strong);
        }

        .status[data-tone="error"] {
            background: var(--danger-soft);
            border-color: rgba(164, 70, 59, 0.18);
            color: var(--danger);
        }

        .json-output {
            margin-top: 16px;
            min-height: 180px;
            padding: 16px 18px;
            border-radius: 20px;
            background: linear-gradient(180deg, #10201d 0%, #172d29 100%);
            border: 1px solid rgba(255, 255, 255, 0.06);
            color: #e9f4f0;
            font-family: "IBM Plex Mono", Consolas, monospace;
            font-size: 0.84rem;
            line-height: 1.65;
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
        }

        .table-wrap {
            margin-top: 16px;
            border-radius: 22px;
            border: 1px solid rgba(24, 38, 35, 0.08);
            background: rgba(255, 255, 255, 0.74);
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.44);
        }

        table {
            min-width: 620px;
        }

        th,
        td {
            padding: 13px 16px;
            border-bottom: 1px solid rgba(24, 38, 35, 0.07);
            text-align: left;
            vertical-align: top;
        }

        th {
            background: rgba(24, 38, 35, 0.04);
            color: var(--muted);
            font-family: "IBM Plex Mono", monospace;
            font-size: 0.73rem;
            font-weight: 600;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }

        tbody tr:hover {
            background: rgba(15, 122, 104, 0.04);
        }

        .empty-state {
            margin: 0;
            padding: 18px;
            border-radius: 18px;
            background: rgba(255, 255, 255, 0.62);
            border: 1px dashed rgba(24, 38, 35, 0.14);
            color: var(--muted);
        }

        .panel[id] {
            scroll-margin-top: 110px;
        }

        .section-nav {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 18px;
        }

        .section-link {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            padding: 10px 14px;
            border-radius: 999px;
            text-decoration: none;
            background: rgba(255, 255, 255, 0.66);
            border: 1px solid rgba(24, 38, 35, 0.08);
            color: var(--ink);
            font-size: 0.88rem;
            font-weight: 700;
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.5);
            transition: transform 140ms ease, border-color 140ms ease, background 140ms ease;
        }

        .section-link:hover {
            transform: translateY(-1px);
            border-color: color-mix(in srgb, var(--accent) 22%, white);
            background: rgba(255, 255, 255, 0.92);
        }

        .journey-strip,
        .ops-grid {
            display: grid;
            gap: 12px;
            margin-top: 18px;
        }

        .journey-strip {
            grid-template-columns: repeat(3, minmax(0, 1fr));
        }

        .ops-grid {
            grid-template-columns: repeat(4, minmax(0, 1fr));
        }

        .command-strip {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 12px;
            margin-top: 18px;
        }

        .journey-step,
        .ops-card,
        .command-card,
        .subpanel {
            position: relative;
            overflow: hidden;
            padding: 16px 18px;
            border-radius: 20px;
            background: rgba(255, 255, 255, 0.68);
            border: 1px solid rgba(24, 38, 35, 0.08);
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.46);
        }

        .journey-step::before,
        .ops-card::before,
        .command-card::before,
        .subpanel::before {
            content: "";
            position: absolute;
            inset: 0 0 auto 0;
            height: 3px;
            background: linear-gradient(90deg, var(--accent), rgba(255, 255, 255, 0));
            opacity: 0.8;
        }

        .journey-step small,
        .ops-card small,
        .command-card small {
            display: block;
            margin-bottom: 10px;
            color: var(--accent-strong);
            font-family: "IBM Plex Mono", monospace;
            font-size: 0.72rem;
            font-weight: 600;
            letter-spacing: 0.12em;
            text-transform: uppercase;
        }

        .journey-step strong,
        .ops-card strong,
        .command-card strong,
        .subpanel h3,
        .phone-shell h3 {
            display: block;
            margin: 0;
            color: var(--ink);
            font-family: "Fraunces", Georgia, serif;
            font-size: 1.08rem;
            letter-spacing: -0.03em;
            line-height: 1.1;
        }

        .journey-step span,
        .ops-card span,
        .command-card span,
        .subpanel p {
            display: block;
            margin-top: 8px;
            color: var(--muted);
            font-size: 0.92rem;
            line-height: 1.65;
        }

        .split-shell {
            display: grid;
            grid-template-columns: minmax(0, 1.15fr) minmax(280px, 0.85fr);
            gap: 16px;
            align-items: start;
        }

        .stack-flow {
            display: grid;
            gap: 14px;
        }

        .micro-list {
            margin: 14px 0 0;
            padding: 0;
            list-style: none;
            display: grid;
            gap: 10px;
        }

        .micro-list li {
            padding: 12px 14px;
            border-radius: 16px;
            background: rgba(255, 255, 255, 0.58);
            border: 1px solid rgba(24, 38, 35, 0.08);
            color: var(--muted);
            line-height: 1.6;
        }

        .phone-shell {
            position: relative;
            overflow: hidden;
            padding: 20px;
            border-radius: 28px;
            background: linear-gradient(180deg, color-mix(in srgb, var(--accent) 76%, #18302b) 0%, #10201d 100%);
            color: #eef6f3;
            border: 1px solid rgba(255, 255, 255, 0.08);
            box-shadow: 0 18px 40px color-mix(in srgb, var(--accent) 24%, transparent);
        }

        .phone-shell::before {
            content: "";
            position: absolute;
            inset: 0;
            background:
                radial-gradient(circle at top right, rgba(255, 255, 255, 0.16), transparent 24%),
                linear-gradient(180deg, rgba(255, 255, 255, 0.08), transparent 40%);
            pointer-events: none;
        }

        .phone-shell h3,
        .phone-shell strong {
            color: #f7fbf9;
        }

        .phone-shell p {
            margin: 8px 0 0;
            color: rgba(238, 246, 243, 0.76);
            line-height: 1.7;
        }

        .phone-chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin: 14px 0 18px;
        }

        .phone-chip {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 8px 10px;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.14);
            font-size: 0.8rem;
            color: #eef6f3;
        }

        .phone-shell .table-wrap {
            background: rgba(255, 255, 255, 0.08);
            border-color: rgba(255, 255, 255, 0.14);
            box-shadow: none;
        }

        .phone-shell .empty-state {
            background: rgba(255, 255, 255, 0.06);
            border-color: rgba(255, 255, 255, 0.16);
            color: rgba(238, 246, 243, 0.82);
        }

        .phone-shell .status {
            background: rgba(255, 255, 255, 0.08);
            border-color: rgba(255, 255, 255, 0.12);
            color: rgba(238, 246, 243, 0.82);
        }

        .panel.span-4 {
            grid-column: span 4;
        }

        .panel.span-5 {
            grid-column: span 5;
        }

        .panel.span-7 {
            grid-column: span 7;
        }

        .panel.span-8 {
            grid-column: span 8;
        }

        button {
            display: inline-flex;
            align-items: center;
            justify-content: center;
        }

        body[data-surface="app"] .page-shell {
            max-width: 780px;
            padding-bottom: 92px;
        }

        body[data-surface="app"] .hero {
            grid-template-columns: minmax(0, 1fr);
        }

        body[data-surface="app"] .hero-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }

        body[data-surface="app"] .surface-grid {
            grid-template-columns: minmax(0, 1fr);
        }

        body[data-surface="app"] .panel {
            grid-column: span 12;
        }

        body[data-surface="app"] .field-grid,
        body[data-surface="app"] .split-shell,
        body[data-surface="app"] .journey-strip {
            grid-template-columns: minmax(0, 1fr);
        }

        body[data-surface="app"] .button-row {
            align-items: stretch;
        }

        body[data-surface="app"] .button-row button {
            flex: 1 1 100%;
        }

        body[data-surface="platform"] .page-shell {
            max-width: 1600px;
        }

        body[data-surface="platform"] .surface-grid {
            gap: 14px;
        }

        body[data-surface="platform"] .panel {
            padding: 20px;
            border-radius: 24px;
        }

        body[data-surface="platform"] .panel-header h2 {
            font-size: 1.3rem;
        }

        body[data-surface="platform"] label {
            font-size: 0.72rem;
        }

        body[data-surface="platform"] .field-grid:not(.single) {
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 10px;
        }

        body[data-surface="platform"] input,
        body[data-surface="platform"] textarea,
        body[data-surface="platform"] select {
            padding: 10px 12px;
            border-radius: 14px;
        }

        body[data-surface="platform"] textarea {
            min-height: 104px;
        }

        body[data-surface="platform"] button {
            min-height: 40px;
            padding: 9px 14px;
            font-size: 0.88rem;
        }

        body[data-surface="platform"] .json-output {
            min-height: 150px;
            max-height: 360px;
        }

        body[data-surface="admin"] .page-shell {
            max-width: 1540px;
        }

        body[data-surface="admin"] .surface-grid {
            gap: 16px;
        }

        body[data-surface="admin"] .panel {
            padding: 21px;
            border-radius: 24px;
        }

        body[data-surface="admin"] .panel-header h2 {
            font-size: 1.34rem;
        }

        body[data-surface="admin"] label {
            font-size: 0.72rem;
        }

        body[data-surface="admin"] .field-grid:not(.single) {
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 10px;
        }

        body[data-surface="admin"] input,
        body[data-surface="admin"] textarea,
        body[data-surface="admin"] select {
            padding: 10px 12px;
            border-radius: 14px;
        }

        body[data-surface="admin"] button {
            min-height: 40px;
            padding: 9px 14px;
            font-size: 0.88rem;
        }

        body[data-surface="admin"] .json-output {
            min-height: 150px;
            max-height: 360px;
        }

        @keyframes shell-rise {
            from {
                opacity: 0;
                transform: translateY(14px);
            }

            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        @media (max-width: 1100px) {
            .masthead {
                position: static;
            }

            .hero-copy h2 {
                max-width: none;
            }

            .ops-grid,
            .journey-strip,
            .command-strip,
            .split-shell {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }

            .panel.span-4,
            .panel.span-5,
            .panel.span-7,
            .panel.span-8 {
                grid-column: span 12;
            }

            body[data-surface="platform"] .field-grid:not(.single),
            body[data-surface="admin"] .field-grid:not(.single) {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }

        @media (max-width: 720px) {
            .page-shell {
                padding: 16px 14px 40px;
            }

            .masthead,
            .hero-card,
            .hero-aside,
            .panel {
                border-radius: 22px;
            }

            .hero-card,
            .hero-aside,
            .panel {
                padding: 18px;
            }

            .hero-copy h2 {
                font-size: clamp(2rem, 10vw, 3rem);
            }

            .hero-grid,
            .ops-grid,
            .journey-strip,
            .command-strip,
            .split-shell,
            .field-grid,
            body[data-surface="platform"] .field-grid:not(.single),
            body[data-surface="admin"] .field-grid:not(.single) {
                grid-template-columns: minmax(0, 1fr);
            }

            .section-link,
            .button-row button {
                width: 100%;
            }

            .table-wrap {
                border-radius: 18px;
            }
        }
    </style>
</head>
<body data-surface=\"__SURFACE__\">
    <div class=\"page-shell\">
        <header class=\"masthead\">
            <div class=\"brand-block\">
                <div class=\"brand-mark\">SP</div>
                <div class=\"brand-copy\">
                    <h1>__BRAND__</h1>
                    <p>__BRAND_COPY__</p>
                </div>
            </div>
            <nav class=\"nav-row\">__NAV__</nav>
        </header>

        <section class=\"hero\">
            <div class=\"hero-card\">
                <div class=\"hero-copy\">
                    <span class=\"hero-kicker\">__HERO_KICKER__</span>
                    <h2>__HERO_TITLE__</h2>
                    <p>__HERO_COPY__</p>
                </div>
                <div class="hero-grid">__HERO_STATS__</div>
            </div>

            <aside class=\"hero-aside\">
                <h3>__HERO_ASIDE_TITLE__</h3>
                <ul>__HERO_ASIDE_ITEMS__</ul>
            </aside>
        </section>

        <main class=\"surface-grid\">__BODY__</main>
    </div>

    <script>
        const pageConfig = __PAGE_CONFIG__;
__COMMON_SCRIPT__
__PAGE_SCRIPT__
    </script>
</body>
</html>
"""

_COMMON_SCRIPT = """
const stockPyUi = (() => {
    const storageKeys = {
        publicBase: "stockpy.ui.public-base",
        adminBase: "stockpy.ui.admin-base",
        accessToken: "stockpy.ui.access-token",
        refreshToken: "stockpy.ui.refresh-token",
        user: "stockpy.ui.user",
        adminToken: "stockpy.ui.admin-token",
        adminRefreshToken: "stockpy.ui.admin-refresh-token",
        adminUser: "stockpy.ui.admin-user",
        adminContext: "stockpy.ui.admin-context",
        adminOperatorId: "stockpy.ui.admin-operator-id"
    };

    function byId(id) {
        return document.getElementById(id);
    }

    function escapeHtml(value) {
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/\"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function normalizeBaseUrl(value) {
        return String(value ?? "").trim().replace(/\\/+$/, "");
    }

    function fallbackBaseUrl(kind) {
        const configured = kind === "admin" ? pageConfig.adminApiBaseUrl : pageConfig.publicApiBaseUrl;
        const normalized = normalizeBaseUrl(configured);
        if (normalized) {
            return normalized;
        }
        if (kind === "admin") {
            const port = window.location.port;
            if (port === "7070" || port === "8000") {
                return `${window.location.protocol}//${window.location.hostname}:8001`;
            }
        }
        return window.location.origin;
    }

    function getBaseUrl(kind) {
        const key = kind === "admin" ? storageKeys.adminBase : storageKeys.publicBase;
        return normalizeBaseUrl(localStorage.getItem(key)) || fallbackBaseUrl(kind);
    }

    function setBaseUrl(kind, value) {
        const key = kind === "admin" ? storageKeys.adminBase : storageKeys.publicBase;
        const normalized = normalizeBaseUrl(value);
        if (normalized) {
            localStorage.setItem(key, normalized);
        } else {
            localStorage.removeItem(key);
        }
        return getBaseUrl(kind);
    }

    function publicApi(path) {
        return getBaseUrl("public") + path;
    }

    function adminApi(path) {
        return getBaseUrl("admin") + path;
    }

    async function requestJson(method, url, options = {}) {
        const headers = new Headers(options.headers || {});
        if (options.body !== undefined) {
            headers.set("Content-Type", "application/json");
        }
        if (options.token) {
            headers.set("Authorization", `Bearer ${options.token}`);
        }
        if (options.operatorId) {
            headers.set("X-Operator-ID", String(options.operatorId));
        }

        const response = await fetch(url, {
            method,
            headers,
            body: options.body !== undefined ? JSON.stringify(options.body) : undefined
        });

        const raw = await response.text();
        let payload = null;
        if (raw) {
            try {
                payload = JSON.parse(raw);
            } catch (_error) {
                payload = raw;
            }
        }

        if (!response.ok) {
            const detail = payload && typeof payload === "object"
                ? payload.detail || payload.message || JSON.stringify(payload)
                : raw || `Request failed (${response.status})`;
            throw new Error(detail);
        }

        return payload;
    }

    function renderJson(id, payload) {
        const node = byId(id);
        if (!node) {
            return;
        }
        if (payload === undefined || payload === null || payload === "") {
            node.textContent = "";
            return;
        }
        node.textContent = typeof payload === "string" ? payload : JSON.stringify(payload, null, 2);
    }

    function setStatus(id, message, tone = "info") {
        const node = byId(id);
        if (!node) {
            return;
        }
        node.dataset.tone = tone;
        node.textContent = message || "";
    }

    function readValue(id) {
        const node = byId(id);
        return node ? node.value.trim() : "";
    }

    function readNumber(id, fallback) {
        const raw = readValue(id);
        if (!raw) {
            return fallback;
        }
        const parsed = Number(raw);
        return Number.isFinite(parsed) ? parsed : fallback;
    }

    function readCheckbox(id) {
        const node = byId(id);
        return Boolean(node && node.checked);
    }

    function getAccessToken() {
        return localStorage.getItem(storageKeys.accessToken) || "";
    }

    function getRefreshToken() {
        return localStorage.getItem(storageKeys.refreshToken) || "";
    }

    function getStoredUser() {
        const raw = localStorage.getItem(storageKeys.user);
        if (!raw) {
            return null;
        }
        try {
            return JSON.parse(raw);
        } catch (_error) {
            return null;
        }
    }

    function setPublicSession(sessionPayload) {
        if (!sessionPayload || !sessionPayload.access_token || !sessionPayload.refresh_token) {
            return;
        }
        localStorage.setItem(storageKeys.accessToken, sessionPayload.access_token);
        localStorage.setItem(storageKeys.refreshToken, sessionPayload.refresh_token);
        if (sessionPayload.user) {
            localStorage.setItem(storageKeys.user, JSON.stringify(sessionPayload.user));
        }
    }

    function clearPublicSession() {
        localStorage.removeItem(storageKeys.accessToken);
        localStorage.removeItem(storageKeys.refreshToken);
        localStorage.removeItem(storageKeys.user);
    }

    function getAdminToken() {
        return localStorage.getItem(storageKeys.adminToken) || "";
    }

    function getAdminRefreshToken() {
        return localStorage.getItem(storageKeys.adminRefreshToken) || "";
    }

    function getAdminStoredUser() {
        const raw = localStorage.getItem(storageKeys.adminUser);
        if (!raw) {
            return null;
        }
        try {
            return JSON.parse(raw);
        } catch (_error) {
            return null;
        }
    }

    function getAdminContext() {
        const raw = localStorage.getItem(storageKeys.adminContext);
        if (!raw) {
            return null;
        }
        try {
            return JSON.parse(raw);
        } catch (_error) {
            return null;
        }
    }

    function getAdminOperatorId() {
        const stored = String(localStorage.getItem(storageKeys.adminOperatorId) || "").trim();
        if (stored) {
            return stored;
        }
        const user = getAdminStoredUser();
        if (user && user.id !== undefined && user.id !== null) {
            return String(user.id);
        }
        return "";
    }

    function setAdminToken(token) {
        const normalized = String(token || "").trim();
        if (normalized) {
            localStorage.setItem(storageKeys.adminToken, normalized);
        } else {
            localStorage.removeItem(storageKeys.adminToken);
        }
        return normalized;
    }

    function setAdminOperatorId(value) {
        const normalized = String(value || "").trim();
        if (normalized) {
            localStorage.setItem(storageKeys.adminOperatorId, normalized);
        } else {
            localStorage.removeItem(storageKeys.adminOperatorId);
        }
        return getAdminOperatorId();
    }

    function setAdminSession(sessionPayload) {
        if (!sessionPayload || !sessionPayload.access_token) {
            return;
        }
        localStorage.setItem(storageKeys.adminToken, sessionPayload.access_token);
        if (sessionPayload.refresh_token) {
            localStorage.setItem(storageKeys.adminRefreshToken, sessionPayload.refresh_token);
        } else {
            localStorage.removeItem(storageKeys.adminRefreshToken);
        }
        if (sessionPayload.user) {
            localStorage.setItem(storageKeys.adminUser, JSON.stringify(sessionPayload.user));
            if (sessionPayload.user.id !== undefined && sessionPayload.user.id !== null) {
                localStorage.setItem(storageKeys.adminOperatorId, String(sessionPayload.user.id));
            }
        }
        if (sessionPayload.admin) {
            localStorage.setItem(storageKeys.adminContext, JSON.stringify(sessionPayload.admin));
        }
    }

    function clearAdminSession() {
        localStorage.removeItem(storageKeys.adminToken);
        localStorage.removeItem(storageKeys.adminRefreshToken);
        localStorage.removeItem(storageKeys.adminUser);
        localStorage.removeItem(storageKeys.adminContext);
        localStorage.removeItem(storageKeys.adminOperatorId);
    }

    function requireAccessToken() {
        const token = getAccessToken();
        if (!token) {
            throw new Error("请先验证用户验证码以获取访问令牌。");
        }
        return token;
    }

    function requireAdminToken() {
        const token = getAdminToken();
        if (!token) {
            throw new Error("请先以管理员操作员身份登录，或粘贴管理 Bearer Token。");
        }
        return token;
    }

    function requireAdminOperatorId() {
        const operatorId = getAdminOperatorId();
        if (!operatorId) {
            throw new Error("此操作必须提供管理员操作员 ID。请先登录，或填写操作员 ID 覆盖值。");
        }
        return operatorId;
    }

    function renderSearchTable(containerId, items) {
        const node = byId(containerId);
        if (!node) {
            return;
        }
        if (!Array.isArray(items) || items.length === 0) {
            node.innerHTML = '<div class="empty-state">当前搜索词没有匹配到任何标的。</div>';
            return;
        }

        const rows = items.map((item) => `
            <tr>
                <td><strong>${escapeHtml(item.symbol)}</strong></td>
                <td>${escapeHtml(item.name || item.name_zh || "")}</td>
                <td>${escapeHtml(item.asset_type || "")}</td>
                <td>${escapeHtml(item.exchange || "")}</td>
                <td><button type="button" class="secondary search-pick" data-symbol="${escapeHtml(item.symbol)}">使用代码</button></td>
            </tr>
        `).join("");

        node.innerHTML = `
            <table>
                <thead>
                    <tr>
                        <th>代码</th>
                        <th>名称</th>
                        <th>类型</th>
                        <th>交易所</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        `;
    }

    function renderSessionSnapshot(targetId) {
        renderJson(targetId, {
            public_api_base_url: getBaseUrl("public"),
            admin_api_base_url: getBaseUrl("admin"),
            access_token_present: Boolean(getAccessToken()),
            refresh_token_present: Boolean(getRefreshToken()),
            stored_user: getStoredUser(),
            admin_token_present: Boolean(getAdminToken()),
            admin_refresh_token_present: Boolean(getAdminRefreshToken()),
            stored_admin_user: getAdminStoredUser(),
            stored_admin_context: getAdminContext(),
            admin_operator_id: getAdminOperatorId()
        });
    }

    function bindBaseForm() {
        const publicInput = byId("public-api-base");
        const adminInput = byId("admin-api-base");
        const saveButton = byId("save-base-urls");

        if (publicInput) {
            publicInput.value = getBaseUrl("public");
        }
        if (adminInput) {
            adminInput.value = getBaseUrl("admin");
        }

        if (saveButton) {
            saveButton.addEventListener("click", () => {
                const savedPublic = setBaseUrl("public", publicInput ? publicInput.value : "");
                const savedAdmin = setBaseUrl("admin", adminInput ? adminInput.value : "");
                setStatus(
                    "base-url-status",
                    `接口地址已保存。Public=${savedPublic} Admin=${savedAdmin}`,
                    "success"
                );
                renderSessionSnapshot("session-output");
                renderSessionSnapshot("platform-session-output");
                renderSessionSnapshot("platform-admin-session-output");
                renderSessionSnapshot("admin-session-output");
            });
        }
    }

    return {
        adminApi,
        bindBaseForm,
        byId,
        clearPublicSession,
        escapeHtml,
        getAccessToken,
        getAdminContext,
        getAdminOperatorId,
        getAdminRefreshToken,
        getAdminStoredUser,
        getAdminToken,
        getBaseUrl,
        getRefreshToken,
        getStoredUser,
        publicApi,
        readCheckbox,
        readNumber,
        readValue,
        clearAdminSession,
        renderJson,
        renderSearchTable,
        renderSessionSnapshot,
        requestJson,
        requireAccessToken,
        requireAdminOperatorId,
        requireAdminToken,
        setAdminSession,
        setAdminOperatorId,
        setAdminToken,
        setPublicSession,
        setStatus
    };
})();

window.stockPyUi = stockPyUi;
window.addEventListener("DOMContentLoaded", () => stockPyUi.bindBaseForm());
"""

_APP_SCRIPT = """
window.addEventListener("DOMContentLoaded", () => {
    const ui = window.stockPyUi;

    const draftStorageKey = "stockpy.ui.subscriber-draft";
    const defaultCash = 0;

    function numberOrZero(value) {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : 0;
    }

    function roundMoney(value) {
        return Math.round((numberOrZero(value) + Number.EPSILON) * 100) / 100;
    }

    function roundRatio(value) {
        return Math.round((numberOrZero(value) + Number.EPSILON) * 10000) / 10000;
    }

    function formatNumber(value) {
        return new Intl.NumberFormat("zh-CN", {
            minimumFractionDigits: 0,
            maximumFractionDigits: 2
        }).format(numberOrZero(value));
    }

    function formatDateTime(value) {
        if (!value) {
            return "未记录";
        }
        const parsed = new Date(value);
        if (Number.isNaN(parsed.getTime())) {
            return String(value);
        }
        return new Intl.DateTimeFormat("zh-CN", {
            dateStyle: "medium",
            timeStyle: "short"
        }).format(parsed);
    }

    function normalizeSymbol(value) {
        return String(value || "").trim().toUpperCase();
    }

    function defaultDraft() {
        return {
            cash: defaultCash,
            currency: "USD",
            allowEmptyPortfolio: false,
            watchlist: [],
            portfolio: [],
            remoteSummary: null,
            lastSavedAt: null,
            lastSyncResponse: null
        };
    }

    function sanitizeWatchlistItem(item) {
        const symbol = normalizeSymbol(item && item.symbol);
        if (!symbol) {
            return null;
        }
        const score = Math.max(0, Math.min(100, Math.round(numberOrZero(item && item.min_score) || 65)));
        return {
            symbol,
            min_score: score,
            notify: item && item.notify !== undefined ? Boolean(item.notify) : true
        };
    }

    function sanitizePortfolioItem(item) {
        const symbol = normalizeSymbol(item && item.symbol);
        const shares = Math.floor(numberOrZero(item && item.shares));
        const avgCost = roundMoney(item && item.avg_cost);
        if (!symbol || shares <= 0 || avgCost <= 0) {
            return null;
        }
        const targetProfit = Math.min(1, Math.max(0.01, roundRatio(item && item.target_profit ? item.target_profit : 0.15)));
        const stopLoss = Math.min(1, Math.max(0.01, roundRatio(item && item.stop_loss ? item.stop_loss : 0.08)));
        return {
            symbol,
            shares,
            avg_cost: avgCost,
            target_profit: targetProfit,
            stop_loss: stopLoss,
            notify: item && item.notify !== undefined ? Boolean(item.notify) : true,
            notes: String((item && item.notes) || "").trim() || null
        };
    }

    function sanitizeDraft(raw) {
        const base = defaultDraft();
        const source = raw && typeof raw === "object" ? raw : {};

        const watchlistMap = new Map();
        const rawWatchlist = Array.isArray(source.watchlist) ? source.watchlist : [];
        rawWatchlist.forEach((item) => {
            const normalized = sanitizeWatchlistItem(item);
            if (normalized) {
                watchlistMap.set(normalized.symbol, normalized);
            }
        });

        const portfolioMap = new Map();
        const rawPortfolio = Array.isArray(source.portfolio) ? source.portfolio : [];
        rawPortfolio.forEach((item) => {
            const normalized = sanitizePortfolioItem(item);
            if (normalized) {
                portfolioMap.set(normalized.symbol, normalized);
            }
        });

        return {
            cash: Math.max(0, roundMoney(source.cash)),
            currency: String(source.currency || base.currency).trim().toUpperCase() || base.currency,
            allowEmptyPortfolio: Boolean(source.allowEmptyPortfolio),
            watchlist: Array.from(watchlistMap.values()).sort((left, right) => left.symbol.localeCompare(right.symbol)),
            portfolio: Array.from(portfolioMap.values()).sort((left, right) => left.symbol.localeCompare(right.symbol)),
            remoteSummary: source.remoteSummary && typeof source.remoteSummary === "object" ? source.remoteSummary : null,
            lastSavedAt: source.lastSavedAt || null,
            lastSyncResponse: source.lastSyncResponse && typeof source.lastSyncResponse === "object" ? source.lastSyncResponse : null
        };
    }

    function loadDraft() {
        try {
            const raw = localStorage.getItem(draftStorageKey);
            return sanitizeDraft(raw ? JSON.parse(raw) : null);
        } catch (_error) {
            return defaultDraft();
        }
    }

    let draft = loadDraft();

    function portfolioCostBasis() {
        return roundMoney(draft.portfolio.reduce((sum, item) => sum + (numberOrZero(item.shares) * numberOrZero(item.avg_cost)), 0));
    }

    function estimatedTotalCapital() {
        return roundMoney(numberOrZero(draft.cash) + portfolioCostBasis());
    }

    function validationMessages() {
        const errors = [];
        if (draft.watchlist.length === 0) {
            errors.push("请至少添加 1 只订阅股票。");
        }
        if (estimatedTotalCapital() <= 0) {
            errors.push("现金与持仓成本合计必须大于 0。");
        }
        if (draft.portfolio.length === 0 && !draft.allowEmptyPortfolio) {
            errors.push("当前没有持仓时，请勾选“我当前是空仓”。");
        }
        return errors;
    }

    function setHtml(id, html) {
        const node = ui.byId(id);
        if (node) {
            node.innerHTML = html;
        }
    }

    function syncInputsFromDraft() {
        const cashInput = ui.byId("draft-cash-input");
        if (cashInput) {
            cashInput.value = draft.cash ? String(draft.cash) : "0";
        }
        const currencyInput = ui.byId("draft-currency-input");
        if (currencyInput) {
            currencyInput.value = draft.currency || "USD";
        }
        const allowEmptyInput = ui.byId("draft-allow-empty-portfolio");
        if (allowEmptyInput) {
            allowEmptyInput.checked = Boolean(draft.allowEmptyPortfolio);
        }
        const storedUser = ui.getStoredUser();
        if (storedUser && storedUser.email) {
            const authEmail = ui.byId("auth-email");
            const verifyEmail = ui.byId("verify-email");
            if (authEmail && !authEmail.value) {
                authEmail.value = storedUser.email;
            }
            if (verifyEmail && !verifyEmail.value) {
                verifyEmail.value = storedUser.email;
            }
        }
        const timezoneInput = ui.byId("verify-timezone");
        if (timezoneInput && !timezoneInput.value) {
            timezoneInput.value = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
        }
    }

    function renderSessionPanel() {
        const user = ui.getStoredUser();
        const remoteSummary = draft.remoteSummary || {};
        if (!user && !remoteSummary.email) {
            setHtml("subscriber-session-panel", '<div class="empty-state">登录后，这里会显示当前账号、套餐和最近一次云端同步状态。</div>');
            return;
        }

        const rows = [
            ["当前账号", user && user.email ? user.email : (remoteSummary.email || "未登录")],
            ["套餐", user && user.plan ? user.plan : (remoteSummary.plan || "未获取")],
            ["语言 / 时区", [user && user.locale, user && user.timezone].filter(Boolean).join(" / ") || [remoteSummary.locale, remoteSummary.timezone].filter(Boolean).join(" / ") || "未设置"],
            ["登录状态", ui.getAccessToken() ? "已保存登录令牌" : "未登录"],
            ["云端订阅状态", remoteSummary.subscriptionStatus || "未读取"],
            ["最近云端同步", formatDateTime(remoteSummary.lastSyncedAt)]
        ];

        const checklist = remoteSummary.checklist;
        const checklistHtml = checklist
            ? `
                <table>
                    <thead>
                        <tr>
                            <th>云端检查项</th>
                            <th>值</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr><td>已配置资金</td><td>${checklist.has_capital ? "是" : "否"}</td></tr>
                        <tr><td>云端订阅股票</td><td>${ui.escapeHtml(checklist.watchlist_count)}</td></tr>
                        <tr><td>云端持仓</td><td>${ui.escapeHtml(checklist.portfolio_count)}</td></tr>
                        <tr><td>推送设备</td><td>${ui.escapeHtml(checklist.push_device_count)}</td></tr>
                    </tbody>
                </table>
            `
            : "";

        setHtml(
            "subscriber-session-panel",
            `
                <table>
                    <thead>
                        <tr>
                            <th>项目</th>
                            <th>当前值</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${rows.map((row) => `<tr><td>${ui.escapeHtml(row[0])}</td><td>${ui.escapeHtml(row[1])}</td></tr>`).join("")}
                    </tbody>
                </table>
                ${checklistHtml}
            `
        );
    }

    function renderSyncNote() {
        const note = ui.byId("draft-sync-note");
        if (!note) {
            return;
        }
        const segments = [];
        if (draft.lastSavedAt) {
            segments.push(`最近保存：${formatDateTime(draft.lastSavedAt)}`);
        }
        if (draft.lastSyncResponse && draft.lastSyncResponse.syncedAt) {
            segments.push(`最近开始订阅：${formatDateTime(draft.lastSyncResponse.syncedAt)}`);
        }
        note.textContent = segments.length
            ? `${segments.join(" | ")} | 浏览器仍会保留离线草稿。`
            : "浏览器会自动保留草稿；只有“开始订阅”时才会把监控快照同步到服务端。";
    }

    function renderSummaryPanel() {
        const errors = validationMessages();
        const summaryRows = [
            ["订阅股票", draft.watchlist.length],
            ["已持仓股票", draft.portfolio.length],
            ["现金", `${formatNumber(draft.cash)} ${ui.escapeHtml(draft.currency)}`],
            ["持仓成本合计", `${formatNumber(portfolioCostBasis())} ${ui.escapeHtml(draft.currency)}`],
            ["估算总资产", `${formatNumber(estimatedTotalCapital())} ${ui.escapeHtml(draft.currency)}`],
            ["空仓启动", draft.allowEmptyPortfolio ? "允许" : "不允许"]
        ];

        const readinessHtml = errors.length
            ? `<div class="empty-state">开始订阅前还需要：${ui.escapeHtml(errors.join("；"))}</div>`
            : '<div class="status" data-tone="success">条件已满足，可以直接开始订阅。</div>';

        setHtml(
            "draft-summary-panel",
            `
                <table>
                    <thead>
                        <tr>
                            <th>草稿项</th>
                            <th>当前值</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${summaryRows.map((row) => `<tr><td>${ui.escapeHtml(row[0])}</td><td>${row[1]}</td></tr>`).join("")}
                    </tbody>
                </table>
                ${readinessHtml}
            `
        );
    }

    function renderWatchlistTable() {
        if (draft.watchlist.length === 0) {
            setHtml("draft-watchlist-table", '<div class="empty-state">还没有订阅股票。加入后，桌面端会把它们作为监控候选列表。</div>');
            return;
        }
        const rows = draft.watchlist.map((item) => `
            <tr>
                <td><strong>${ui.escapeHtml(item.symbol)}</strong></td>
                <td>${ui.escapeHtml(item.min_score)}</td>
                <td>${item.notify ? "开启" : "关闭"}</td>
                <td><button type="button" class="ghost" data-watchlist-remove="${ui.escapeHtml(item.symbol)}">删除</button></td>
            </tr>
        `).join("");
        setHtml(
            "draft-watchlist-table",
            `
                <table>
                    <thead>
                        <tr>
                            <th>代码</th>
                            <th>过滤分数</th>
                            <th>通知</th>
                            <th>操作</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            `
        );
    }

    function fillPortfolioForm(item) {
        if (!item) {
            return;
        }
        const mapping = {
            "draft-portfolio-symbol": item.symbol,
            "draft-portfolio-shares": item.shares,
            "draft-portfolio-cost": item.avg_cost,
            "draft-portfolio-target": item.target_profit,
            "draft-portfolio-stop": item.stop_loss,
            "draft-portfolio-notes": item.notes || ""
        };
        Object.entries(mapping).forEach(([id, value]) => {
            const node = ui.byId(id);
            if (node) {
                node.value = value;
            }
        });
        const notifyNode = ui.byId("draft-portfolio-notify");
        if (notifyNode) {
            notifyNode.checked = Boolean(item.notify);
        }
        ui.setStatus("portfolio-draft-status", `已将 ${item.symbol} 填回表单，可直接修改后再次保存。`, "success");
    }

    function renderPortfolioTable() {
        if (draft.portfolio.length === 0) {
            setHtml("draft-portfolio-table", '<div class="empty-state">还没有已持仓股票。如果当前空仓，请在开始订阅前勾选“允许空仓启动”。</div>');
            return;
        }
        const rows = draft.portfolio.map((item) => `
            <tr>
                <td><strong>${ui.escapeHtml(item.symbol)}</strong></td>
                <td>${ui.escapeHtml(item.shares)}</td>
                <td>${formatNumber(item.avg_cost)}</td>
                <td>${formatNumber(roundMoney(item.shares * item.avg_cost))}</td>
                <td>${item.notify ? "开启" : "关闭"}</td>
                <td>
                    <button type="button" class="secondary" data-portfolio-edit="${ui.escapeHtml(item.symbol)}">编辑</button>
                    <button type="button" class="ghost" data-portfolio-remove="${ui.escapeHtml(item.symbol)}">删除</button>
                </td>
            </tr>
        `).join("");
        setHtml(
            "draft-portfolio-table",
            `
                <table>
                    <thead>
                        <tr>
                            <th>代码</th>
                            <th>数量</th>
                            <th>均价</th>
                            <th>持仓成本</th>
                            <th>通知</th>
                            <th>操作</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            `
        );
    }

    function buildSubscriptionPayload() {
        const errors = validationMessages();
        if (errors.length) {
            throw new Error(errors.join("；"));
        }
        return {
            allow_empty_portfolio: draft.portfolio.length === 0 && Boolean(draft.allowEmptyPortfolio),
            account: {
                total_capital: estimatedTotalCapital(),
                currency: draft.currency || "USD"
            },
            watchlist: draft.watchlist.map((item) => ({
                symbol: item.symbol,
                min_score: item.min_score,
                notify: item.notify
            })),
            portfolio: draft.portfolio.map((item) => ({
                symbol: item.symbol,
                shares: item.shares,
                avg_cost: item.avg_cost,
                target_profit: item.target_profit,
                stop_loss: item.stop_loss,
                notify: item.notify,
                notes: item.notes
            }))
        };
    }

    function renderSubscriptionPanel() {
        const errors = validationMessages();
        const payload = {
            allow_empty_portfolio: draft.portfolio.length === 0 && Boolean(draft.allowEmptyPortfolio),
            account: {
                total_capital: estimatedTotalCapital(),
                currency: draft.currency || "USD"
            },
            watchlist: draft.watchlist,
            portfolio: draft.portfolio
        };
        const latestResponse = draft.lastSyncResponse
            ? `
                <h3>最近一次开始订阅结果</h3>
                <pre class="json-output">${ui.escapeHtml(JSON.stringify(draft.lastSyncResponse.response, null, 2))}</pre>
            `
            : "";

        setHtml(
            "subscription-sync-panel",
            `
                <table>
                    <thead>
                        <tr>
                            <th>同步项</th>
                            <th>当前值</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr><td>现金</td><td>${formatNumber(draft.cash)} ${ui.escapeHtml(draft.currency)}</td></tr>
                        <tr><td>持仓成本</td><td>${formatNumber(portfolioCostBasis())} ${ui.escapeHtml(draft.currency)}</td></tr>
                        <tr><td>估算总资产</td><td>${formatNumber(estimatedTotalCapital())} ${ui.escapeHtml(draft.currency)}</td></tr>
                        <tr><td>订阅股票数</td><td>${ui.escapeHtml(draft.watchlist.length)}</td></tr>
                        <tr><td>持仓数</td><td>${ui.escapeHtml(draft.portfolio.length)}</td></tr>
                    </tbody>
                </table>
                ${errors.length ? `<div class="empty-state">当前还不能开始订阅：${ui.escapeHtml(errors.join("；"))}</div>` : '<div class="status" data-tone="success">已具备开始订阅条件。</div>'}
                <h3>即将同步的请求</h3>
                <pre class="json-output">${ui.escapeHtml(JSON.stringify(payload, null, 2))}</pre>
                ${latestResponse}
            `
        );
    }

    function renderMetric(id, value) {
        const node = ui.byId(id);
        if (node) {
            node.textContent = String(value);
        }
    }

    function renderAll() {
        syncInputsFromDraft();
        renderMetric("draft-watchlist-count", draft.watchlist.length);
        renderMetric("draft-portfolio-count", draft.portfolio.length);
        renderMetric("draft-cash-amount", formatNumber(draft.cash));
        renderMetric("draft-total-assets", formatNumber(estimatedTotalCapital()));
        renderSessionPanel();
        renderSummaryPanel();
        renderWatchlistTable();
        renderPortfolioTable();
        renderSubscriptionPanel();
        renderSyncNote();
    }

    function persistDraft(options = {}) {
        draft = sanitizeDraft(draft);
        draft.lastSavedAt = new Date().toISOString();
        localStorage.setItem(draftStorageKey, JSON.stringify(draft));
        renderAll();
        if (!options.quiet) {
            ui.setStatus(options.statusId || "draft-status", options.message || "草稿已保存到当前浏览器。", options.tone || "success");
        }
    }

    function resetPortfolioForm() {
        const defaults = {
            "draft-portfolio-symbol": "",
            "draft-portfolio-shares": "10",
            "draft-portfolio-cost": "150",
            "draft-portfolio-target": "0.15",
            "draft-portfolio-stop": "0.08",
            "draft-portfolio-notes": ""
        };
        Object.entries(defaults).forEach(([id, value]) => {
            const node = ui.byId(id);
            if (node) {
                node.value = value;
            }
        });
        const notifyNode = ui.byId("draft-portfolio-notify");
        if (notifyNode) {
            notifyNode.checked = true;
        }
    }

    function parseBulkSymbols(raw) {
        const map = new Map();
        String(raw || "")
            .split(/[\\s,，；;]+/)
            .map((item) => normalizeSymbol(item))
            .filter(Boolean)
            .forEach((symbol) => {
                if (!map.has(symbol)) {
                    map.set(symbol, symbol);
                }
            });
        return Array.from(map.values());
    }

    function readRequiredPositiveInteger(id, label) {
        const raw = ui.readValue(id);
        const value = Number(raw);
        if (!Number.isInteger(value) || value <= 0) {
            throw new Error(`${label} 必须是正整数。`);
        }
        return value;
    }

    function readRequiredPositiveNumber(id, label) {
        const raw = ui.readValue(id);
        const value = Number(raw);
        if (!Number.isFinite(value) || value <= 0) {
            throw new Error(`${label} 必须大于 0。`);
        }
        return value;
    }

    async function requestProtected(method, path, options = {}) {
        return await ui.requestJson(method, ui.publicApi(path), {
            token: ui.requireAccessToken(),
            body: options.body
        });
    }

    const sendCodeForm = ui.byId("send-code-form");
    if (sendCodeForm) {
        sendCodeForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("auth-status", "正在发送验证码...");
            try {
                const payload = await ui.requestJson("POST", ui.publicApi("/v1/auth/send-code"), {
                    body: { email: ui.readValue("auth-email") }
                });
                if (payload && payload.dev_code && ui.byId("verify-code")) {
                    ui.byId("verify-code").value = payload.dev_code;
                }
                if (ui.byId("verify-email")) {
                    ui.byId("verify-email").value = ui.readValue("auth-email");
                }
                ui.setStatus("auth-status", payload.message || "验证码已发送。", "success");
            } catch (error) {
                ui.setStatus("auth-status", error.message, "error");
            }
        });
    }

    const verifyForm = ui.byId("verify-form");
    if (verifyForm) {
        verifyForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("auth-status", "正在验证验证码...");
            try {
                const payload = await ui.requestJson("POST", ui.publicApi("/v1/auth/verify"), {
                    body: {
                        email: ui.readValue("verify-email"),
                        code: ui.readValue("verify-code"),
                        locale: ui.readValue("verify-locale") || null,
                        timezone: ui.readValue("verify-timezone") || null
                    }
                });
                ui.setPublicSession(payload);
                renderAll();
                ui.setStatus("auth-status", "登录成功，当前浏览器已保存订阅会话。", "success");
            } catch (error) {
                ui.setStatus("auth-status", error.message, "error");
            }
        });
    }

    const refreshButton = ui.byId("refresh-session");
    if (refreshButton) {
        refreshButton.addEventListener("click", async () => {
            ui.setStatus("auth-status", "正在刷新会话...");
            try {
                const payload = await ui.requestJson("POST", ui.publicApi("/v1/auth/refresh"), {
                    body: { refresh_token: ui.getRefreshToken() }
                });
                ui.setPublicSession(payload);
                renderAll();
                ui.setStatus("auth-status", "登录令牌已刷新。", "success");
            } catch (error) {
                ui.setStatus("auth-status", error.message, "error");
            }
        });
    }

    const logoutButton = ui.byId("logout-session");
    if (logoutButton) {
        logoutButton.addEventListener("click", async () => {
            ui.setStatus("auth-status", "正在退出登录...");
            try {
                await ui.requestJson("POST", ui.publicApi("/v1/auth/logout"), {
                    token: ui.requireAccessToken()
                });
                ui.clearPublicSession();
                renderAll();
                ui.setStatus("auth-status", "已退出登录，本地草稿仍然保留。", "success");
            } catch (error) {
                ui.setStatus("auth-status", error.message, "error");
            }
        });
    }

    const restoreRemoteDraftButton = ui.byId("restore-remote-draft");
    if (restoreRemoteDraftButton) {
        restoreRemoteDraftButton.addEventListener("click", async () => {
            ui.setStatus("auth-status", "正在从云端恢复资料...");
            try {
                const [profile, dashboard, watchlist, portfolio] = await Promise.all([
                    requestProtected("GET", "/v1/account/profile"),
                    requestProtected("GET", "/v1/account/dashboard"),
                    requestProtected("GET", "/v1/watchlist"),
                    requestProtected("GET", "/v1/portfolio")
                ]);
                const cloudPortfolio = Array.isArray(portfolio) ? portfolio : [];
                const costBasis = roundMoney(cloudPortfolio.reduce((sum, item) => sum + numberOrZero(item.total_capital || (item.shares * item.avg_cost)), 0));
                const availableCash = dashboard && dashboard.account && dashboard.account.available_cash !== undefined
                    ? roundMoney(dashboard.account.available_cash)
                    : Math.max(0, roundMoney(numberOrZero(profile && profile.account && profile.account.total_capital) - costBasis));

                draft = sanitizeDraft({
                    ...draft,
                    cash: availableCash,
                    currency: (profile && profile.account && profile.account.currency) || (dashboard && dashboard.account && dashboard.account.currency) || draft.currency,
                    allowEmptyPortfolio: cloudPortfolio.length === 0,
                    watchlist: (Array.isArray(watchlist) ? watchlist : []).map((item) => ({
                        symbol: item.symbol,
                        min_score: item.min_score,
                        notify: item.notify
                    })),
                    portfolio: cloudPortfolio.map((item) => ({
                        symbol: item.symbol,
                        shares: item.shares,
                        avg_cost: item.avg_cost,
                        target_profit: item.target_profit,
                        stop_loss: item.stop_loss,
                        notify: item.notify,
                        notes: item.notes
                    })),
                    remoteSummary: {
                        email: profile && profile.user ? profile.user.email : null,
                        plan: profile && profile.user ? profile.user.plan : null,
                        locale: profile && profile.user ? profile.user.locale : null,
                        timezone: profile && profile.user ? profile.user.timezone : null,
                        subscriptionStatus: dashboard && dashboard.subscription ? dashboard.subscription.status : null,
                        startedAt: dashboard && dashboard.subscription ? dashboard.subscription.started_at : null,
                        lastSyncedAt: dashboard && dashboard.subscription ? dashboard.subscription.last_synced_at : null,
                        lastSyncReason: dashboard && dashboard.subscription ? dashboard.subscription.last_sync_reason : null,
                        checklist: dashboard && dashboard.subscription ? dashboard.subscription.checklist : null,
                        restoredAt: new Date().toISOString()
                    }
                });
                persistDraft({ quiet: true });
                ui.setStatus("auth-status", "已把云端订阅资料恢复到本地草稿。", "success");
            } catch (error) {
                ui.setStatus("auth-status", error.message, "error");
            }
        });
    }

    const saveDraftButton = ui.byId("save-local-draft");
    if (saveDraftButton) {
        saveDraftButton.addEventListener("click", () => {
            persistDraft({ message: "本地订阅草稿已保存。", statusId: "draft-status" });
        });
    }

    const clearDraftButton = ui.byId("clear-local-draft");
    if (clearDraftButton) {
        clearDraftButton.addEventListener("click", () => {
            if (!window.confirm("确定清空当前浏览器里的订阅草稿吗？此操作不会删除云端数据。")) {
                return;
            }
            draft = defaultDraft();
            localStorage.removeItem(draftStorageKey);
            renderAll();
            ui.setStatus("draft-status", "本地订阅草稿已清空。", "success");
        });
    }

    const cashInput = ui.byId("draft-cash-input");
    if (cashInput) {
        cashInput.addEventListener("input", () => {
            draft.cash = Math.max(0, roundMoney(cashInput.value));
            persistDraft({ quiet: true });
        });
    }

    const currencyInput = ui.byId("draft-currency-input");
    if (currencyInput) {
        currencyInput.addEventListener("input", () => {
            draft.currency = String(currencyInput.value || "USD").trim().toUpperCase() || "USD";
            persistDraft({ quiet: true });
        });
    }

    const allowEmptyInput = ui.byId("draft-allow-empty-portfolio");
    if (allowEmptyInput) {
        allowEmptyInput.addEventListener("change", () => {
            draft.allowEmptyPortfolio = Boolean(allowEmptyInput.checked);
            persistDraft({ quiet: true });
        });
    }

    const watchlistForm = ui.byId("draft-watchlist-form");
    if (watchlistForm) {
        watchlistForm.addEventListener("submit", (event) => {
            event.preventDefault();
            try {
                const symbols = parseBulkSymbols(ui.readValue("draft-watchlist-symbols"));
                if (symbols.length === 0) {
                    throw new Error("请至少输入 1 个股票代码。支持逗号、空格或换行分隔。");
                }
                const minScore = Math.max(0, Math.min(100, Math.round(numberOrZero(ui.readValue("draft-watchlist-score")) || 65)));
                const notify = ui.readCheckbox("draft-watchlist-notify");
                const merged = new Map(draft.watchlist.map((item) => [item.symbol, item]));
                symbols.forEach((symbol) => {
                    merged.set(symbol, {
                        symbol,
                        min_score: minScore,
                        notify
                    });
                });
                draft.watchlist = Array.from(merged.values());
                const watchlistInput = ui.byId("draft-watchlist-symbols");
                if (watchlistInput) {
                    watchlistInput.value = "";
                }
                persistDraft({ message: `已加入 ${symbols.length} 只订阅股票。`, statusId: "watchlist-draft-status" });
            } catch (error) {
                ui.setStatus("watchlist-draft-status", error.message, "error");
            }
        });
    }

    const watchlistTable = ui.byId("draft-watchlist-table");
    if (watchlistTable) {
        watchlistTable.addEventListener("click", (event) => {
            const button = event.target.closest("[data-watchlist-remove]");
            if (!button) {
                return;
            }
            const symbol = normalizeSymbol(button.getAttribute("data-watchlist-remove"));
            draft.watchlist = draft.watchlist.filter((item) => item.symbol !== symbol);
            persistDraft({ message: `已从草稿删除 ${symbol}。`, statusId: "watchlist-draft-status" });
        });
    }

    const portfolioForm = ui.byId("draft-portfolio-form");
    if (portfolioForm) {
        portfolioForm.addEventListener("submit", (event) => {
            event.preventDefault();
            try {
                const item = sanitizePortfolioItem({
                    symbol: ui.readValue("draft-portfolio-symbol"),
                    shares: readRequiredPositiveInteger("draft-portfolio-shares", "持股数量"),
                    avg_cost: readRequiredPositiveNumber("draft-portfolio-cost", "持仓均价"),
                    target_profit: readRequiredPositiveNumber("draft-portfolio-target", "止盈目标"),
                    stop_loss: readRequiredPositiveNumber("draft-portfolio-stop", "止损阈值"),
                    notify: ui.readCheckbox("draft-portfolio-notify"),
                    notes: ui.readValue("draft-portfolio-notes")
                });
                if (!item) {
                    throw new Error("请完整填写有效的持仓信息。");
                }
                const merged = new Map(draft.portfolio.map((entry) => [entry.symbol, entry]));
                merged.set(item.symbol, item);
                draft.portfolio = Array.from(merged.values());
                persistDraft({ message: `已保存 ${item.symbol} 的持仓草稿。`, statusId: "portfolio-draft-status" });
                resetPortfolioForm();
            } catch (error) {
                ui.setStatus("portfolio-draft-status", error.message, "error");
            }
        });
    }

    const resetPortfolioButton = ui.byId("reset-portfolio-form");
    if (resetPortfolioButton) {
        resetPortfolioButton.addEventListener("click", () => {
            resetPortfolioForm();
            ui.setStatus("portfolio-draft-status", "持仓表单已重置。", "success");
        });
    }

    const portfolioTable = ui.byId("draft-portfolio-table");
    if (portfolioTable) {
        portfolioTable.addEventListener("click", (event) => {
            const editButton = event.target.closest("[data-portfolio-edit]");
            if (editButton) {
                const symbol = normalizeSymbol(editButton.getAttribute("data-portfolio-edit"));
                const item = draft.portfolio.find((entry) => entry.symbol === symbol);
                fillPortfolioForm(item);
                return;
            }
            const removeButton = event.target.closest("[data-portfolio-remove]");
            if (!removeButton) {
                return;
            }
            const symbol = normalizeSymbol(removeButton.getAttribute("data-portfolio-remove"));
            draft.portfolio = draft.portfolio.filter((item) => item.symbol !== symbol);
            persistDraft({ message: `已从草稿删除 ${symbol} 持仓。`, statusId: "portfolio-draft-status" });
        });
    }

    const startSubscriptionButton = ui.byId("start-subscription-button");
    if (startSubscriptionButton) {
        startSubscriptionButton.addEventListener("click", async () => {
            ui.setStatus("subscription-sync-status", "正在同步订阅快照...");
            try {
                const payload = buildSubscriptionPayload();
                const response = await requestProtected("POST", "/v1/account/start-subscription", { body: payload });
                draft.lastSyncResponse = {
                    syncedAt: new Date().toISOString(),
                    payload,
                    response
                };
                draft.remoteSummary = {
                    ...(draft.remoteSummary || {}),
                    email: (draft.remoteSummary && draft.remoteSummary.email) || (ui.getStoredUser() && ui.getStoredUser().email) || null,
                    plan: (draft.remoteSummary && draft.remoteSummary.plan) || (ui.getStoredUser() && ui.getStoredUser().plan) || null,
                    locale: (draft.remoteSummary && draft.remoteSummary.locale) || (ui.getStoredUser() && ui.getStoredUser().locale) || null,
                    timezone: (draft.remoteSummary && draft.remoteSummary.timezone) || (ui.getStoredUser() && ui.getStoredUser().timezone) || null,
                    subscriptionStatus: response && response.subscription ? response.subscription.status : "active",
                    lastSyncedAt: draft.lastSyncResponse.syncedAt,
                    lastSyncReason: response && response.message ? response.message : "订阅已开始",
                    checklist: response && response.subscription ? response.subscription.checklist : (draft.remoteSummary && draft.remoteSummary.checklist) || null
                };
                persistDraft({ quiet: true });
                ui.setStatus("subscription-sync-status", response.message || "订阅已开始，监控快照已同步。", "success");
            } catch (error) {
                ui.setStatus("subscription-sync-status", error.message, "error");
            }
        });
    }

    resetPortfolioForm();
    renderAll();
});
"""

_PLATFORM_SCRIPT = """
window.addEventListener("DOMContentLoaded", () => {
    const ui = window.stockPyUi;

    function endpoint(method, path, title, options = {}) {
        return {
            key: `${method} ${path}`,
            method,
            path,
            title,
            auth: options.auth || "none",
            base: options.base || "public",
            notes: options.notes || "",
            pathParams: options.pathParams || null,
            query: options.query || null,
            body: options.body || null
        };
    }

    const PLATFORM_ENDPOINTS = [
        endpoint("POST", "/v1/auth/send-code", "发送用户验证码", {
            notes: "邮箱验证码登录第一步。",
            body: { email: "user@example.com" }
        }),
        endpoint("POST", "/v1/auth/verify", "验证验证码并换取会话", {
            notes: "成功后返回 access_token 与 refresh_token。",
            body: {
                email: "user@example.com",
                code: "123456",
                locale: "zh-CN",
                timezone: "Asia/Shanghai"
            }
        }),
        endpoint("POST", "/v1/auth/refresh", "刷新用户会话", {
            notes: "使用 refresh_token 获取新的 access_token。",
            body: { refresh_token: "paste-refresh-token" }
        }),
        endpoint("POST", "/v1/auth/logout", "退出用户会话", {
            auth: "optional",
            notes: "可携带 Bearer Token 与 refresh_token 一并注销。",
            body: { refresh_token: "paste-refresh-token" }
        }),
        endpoint("GET", "/v1/account/profile", "读取账户资料", {
            auth: "bearer"
        }),
        endpoint("GET", "/v1/account/dashboard", "读取账户仪表盘", {
            auth: "bearer"
        }),
        endpoint("PUT", "/v1/account/profile", "更新账户资料", {
            auth: "bearer",
            body: {
                display_name: "Nico",
                locale: "zh-CN",
                timezone: "Asia/Shanghai"
            }
        }),
        endpoint("POST", "/v1/account/start-subscription", "开始订阅并同步快照", {
            auth: "bearer",
            body: {
                allow_empty_portfolio: false,
                account: {
                    total_capital: 5000,
                    currency: "USD"
                },
                watchlist: [
                    {
                        symbol: "AAPL",
                        min_score: 70,
                        notify: true
                    }
                ],
                portfolio: [
                    {
                        symbol: "AAPL",
                        shares: 10,
                        avg_cost: 150,
                        target_profit: 0.2,
                        stop_loss: 0.08,
                        notify: true,
                        notes: "长期持有"
                    }
                ]
            }
        }),
        endpoint("GET", "/v1/watchlist", "读取观察列表", {
            auth: "bearer"
        }),
        endpoint("POST", "/v1/watchlist", "新增观察项", {
            auth: "bearer",
            body: {
                symbol: "TSLA",
                min_score: 70,
                notify: true
            }
        }),
        endpoint("PUT", "/v1/watchlist/{item_id}", "更新观察项", {
            auth: "bearer",
            pathParams: { item_id: 1 },
            body: {
                min_score: 80,
                notify: false
            }
        }),
        endpoint("DELETE", "/v1/watchlist/{item_id}", "删除观察项", {
            auth: "bearer",
            pathParams: { item_id: 1 }
        }),
        endpoint("GET", "/v1/portfolio", "读取持仓", {
            auth: "bearer"
        }),
        endpoint("POST", "/v1/portfolio", "新增持仓", {
            auth: "bearer",
            body: {
                symbol: "AAPL",
                shares: 10,
                avg_cost: 150,
                target_profit: 0.2,
                stop_loss: 0.08,
                notify: true,
                notes: "逢低建仓"
            }
        }),
        endpoint("PUT", "/v1/portfolio/{item_id}", "更新持仓", {
            auth: "bearer",
            pathParams: { item_id: 1 },
            body: {
                shares: 12,
                avg_cost: 148,
                notify: true,
                notes: "补仓"
            }
        }),
        endpoint("DELETE", "/v1/portfolio/{item_id}", "删除持仓", {
            auth: "bearer",
            pathParams: { item_id: 1 }
        }),
        endpoint("GET", "/v1/search/symbols", "搜索标的", {
            query: {
                q: "AAPL",
                limit: 20,
                type: "stock"
            }
        }),
        endpoint("GET", "/v1/notifications", "拉取通知列表", {
            auth: "bearer",
            query: {
                cursor: "",
                limit: 20
            }
        }),
        endpoint("GET", "/v1/notifications/push-devices", "读取推送设备", {
            auth: "bearer"
        }),
        endpoint("POST", "/v1/notifications/push-devices", "注册推送设备", {
            auth: "bearer",
            body: {
                device_id: "web-device-1",
                platform: "web",
                endpoint: "https://example.push/endpoint",
                p256dh: "base64-public-key",
                auth_secret: "base64-auth-secret"
            }
        }),
        endpoint("DELETE", "/v1/notifications/push-devices/{device_id}", "停用推送设备", {
            auth: "bearer",
            pathParams: { device_id: "web-device-1" }
        }),
        endpoint("POST", "/v1/notifications/push-devices/{device_id}/test", "发送推送测试", {
            auth: "bearer",
            pathParams: { device_id: "web-device-1" }
        }),
        endpoint("PUT", "/v1/notifications/read-all", "全部标记已读", {
            auth: "bearer"
        }),
        endpoint("PUT", "/v1/notifications/{notification_id}/read", "单条标记已读", {
            auth: "bearer",
            pathParams: { notification_id: "notif-123" }
        }),
        endpoint("PUT", "/v1/notifications/{notification_id}/ack", "确认单条通知", {
            auth: "bearer",
            pathParams: { notification_id: "notif-123" }
        }),
        endpoint("GET", "/v1/trades/{trade_id}/info", "读取公开交易信息", {
            auth: "public-token",
            pathParams: { trade_id: "trade-123" },
            query: { t: "token-123" }
        }),
        endpoint("GET", "/v1/trades/{trade_id}/app-info", "读取已登录交易信息", {
            auth: "bearer",
            pathParams: { trade_id: "trade-123" }
        }),
        endpoint("GET", "/v1/trades/{trade_id}/confirm", "读取公开确认页内容", {
            auth: "public-token",
            pathParams: { trade_id: "trade-123" },
            query: {
                action: "accept",
                t: "token-123"
            }
        }),
        endpoint("POST", "/v1/trades/{trade_id}/confirm", "公开确认交易", {
            auth: "public-token",
            pathParams: { trade_id: "trade-123" },
            query: {
                action: "accept",
                t: "token-123"
            }
        }),
        endpoint("POST", "/v1/trades/{trade_id}/ignore", "公开忽略交易", {
            auth: "public-token",
            pathParams: { trade_id: "trade-123" },
            query: { t: "token-123" }
        }),
        endpoint("POST", "/v1/trades/{trade_id}/adjust", "公开调整并确认交易", {
            auth: "public-token",
            pathParams: { trade_id: "trade-123" },
            query: { t: "token-123" },
            body: {
                actual_shares: 10,
                actual_price: 150
            }
        }),
        endpoint("POST", "/v1/trades/{trade_id}/app-confirm", "已登录确认交易", {
            auth: "bearer",
            pathParams: { trade_id: "trade-123" }
        }),
        endpoint("POST", "/v1/trades/{trade_id}/app-ignore", "已登录忽略交易", {
            auth: "bearer",
            pathParams: { trade_id: "trade-123" }
        }),
        endpoint("POST", "/v1/trades/{trade_id}/app-adjust", "已登录调整并确认交易", {
            auth: "bearer",
            pathParams: { trade_id: "trade-123" },
            body: {
                actual_shares: 10,
                actual_price: 150
            }
        }),
        endpoint("GET", "/v1/admin/analytics/overview", "读取策略总览", {
            base: "admin",
            auth: "admin-bearer",
            notes: "桌面端策略实验总览。",
            query: {
                window_hours: 24
            }
        }),
        endpoint("GET", "/v1/admin/analytics/strategy-health", "读取策略健康度", {
            base: "admin",
            auth: "admin-bearer",
            notes: "桌面端直接查看策略健康度。",
            query: {
                window_hours: 24
            }
        }),
        endpoint("GET", "/v1/admin/signal-stats/summary", "读取信号摘要", {
            base: "admin",
            auth: "admin-bearer",
            notes: "桌面端快速查看信号生成状态。",
            query: {
                window_hours: 24
            }
        }),
        endpoint("GET", "/v1/admin/scanner/observability", "读取扫描器可观测性", {
            base: "admin",
            auth: "admin-bearer",
            notes: "平台端直接查看 scanner 运行概览。",
            query: {
                status: "",
                symbol: "",
                decision: "",
                limit: 25,
                decision_limit: 25
            }
        }),
        endpoint("GET", "/v1/admin/scanner/live-decision", "读取扫描器实时决策", {
            base: "admin",
            auth: "admin-bearer",
            notes: "从平台端下钻到最近实时决策。",
            query: {
                symbol: "",
                decision: "",
                suppressed: "",
                limit: 25
            }
        }),
        endpoint("GET", "/v1/admin/backtests/runs", "读取回测运行列表", {
            base: "admin",
            auth: "admin-bearer",
            notes: "桌面端实验工作台的回测运行列表。",
            query: {
                status: "",
                strategy_name: "",
                timeframe: "1d",
                symbol: "",
                limit: 25
            }
        }),
        endpoint("GET", "/v1/admin/backtests/rankings/latest", "读取最新回测排名", {
            base: "admin",
            auth: "admin-bearer",
            notes: "直接在桌面端查看策略排名。",
            query: {
                timeframe: "1d",
                limit: 20
            }
        }),
        endpoint("POST", "/v1/admin/backtests/runs", "触发回测排名刷新", {
            base: "admin",
            auth: "admin-bearer",
            notes: "从平台端直接触发新的回测刷新任务。",
            body: {
                symbols: ["AAPL", "MSFT"],
                strategy_names: ["momentum"],
                windows: [30, 90, 180],
                timeframe: "1d"
            }
        })
    ];

    const endpointByKey = new Map(PLATFORM_ENDPOINTS.map((spec) => [spec.key, spec]));

    function authLabel(auth) {
        if (auth === "bearer") {
            return "Bearer";
        }
        if (auth === "admin-bearer") {
            return "Admin Bearer";
        }
        if (auth === "public-token") {
            return "公开 Token";
        }
        if (auth === "optional") {
            return "可选 Bearer";
        }
        return "无需认证";
    }

    function scopeLabel(path) {
        const segments = String(path || "").split("/").filter(Boolean);
        if (segments[0] === "v1" && segments[1] === "admin" && segments[2]) {
            return segments[2];
        }
        if (segments[0] === "v1" && segments[1]) {
            return segments[1];
        }
        return segments[0] || "misc";
    }

    function parseJsonInput(id, label) {
        const raw = ui.readValue(id);
        if (!raw) {
            return null;
        }
        try {
            return JSON.parse(raw);
        } catch (error) {
            throw new Error(`${label} 不是合法 JSON：${error.message}`);
        }
    }

    function parseJsonObjectInput(id, label) {
        const parsed = parseJsonInput(id, label);
        if (parsed === null) {
            return {};
        }
        if (typeof parsed !== "object" || Array.isArray(parsed)) {
            throw new Error(`${label} 必须是 JSON 对象。`);
        }
        return parsed;
    }

    function setJsonField(id, value) {
        const node = ui.byId(id);
        if (!node) {
            return;
        }
        if (value === null || value === undefined) {
            node.value = "";
            return;
        }
        if (typeof value === "object" && !Array.isArray(value) && Object.keys(value).length === 0) {
            node.value = "";
            return;
        }
        node.value = JSON.stringify(value, null, 2);
    }

    function applyPathParams(pathTemplate, params) {
        return pathTemplate.replace(/\\{([^}]+)\\}/g, (_, name) => {
            const value = params[name];
            if (value === undefined || value === null || String(value).trim() === "") {
                throw new Error(`缺少路径参数 ${name}。`);
            }
            return encodeURIComponent(String(value));
        });
    }

    function buildQueryString(params) {
        const searchParams = new URLSearchParams();
        Object.entries(params || {}).forEach(([key, value]) => {
            if (value === undefined || value === null || value === "") {
                return;
            }
            if (Array.isArray(value)) {
                value.forEach((item) => {
                    if (item !== undefined && item !== null && item !== "") {
                        searchParams.append(key, String(item));
                    }
                });
                return;
            }
            searchParams.append(key, String(value));
        });
        return searchParams.toString();
    }

    function populatePlatformEndpointSelect() {
        const select = ui.byId("platform-endpoint-select");
        if (!select) {
            return;
        }
        select.innerHTML = PLATFORM_ENDPOINTS.map(
            (spec) => `<option value="${ui.escapeHtml(spec.key)}">${ui.escapeHtml(spec.key)} - ${ui.escapeHtml(spec.title)}</option>`
        ).join("");
        if (PLATFORM_ENDPOINTS.length > 0) {
            select.value = PLATFORM_ENDPOINTS[0].key;
        }
    }

    function currentEndpointSpec() {
        const selectedKey = ui.readValue("platform-endpoint-select");
        if (!selectedKey) {
            return PLATFORM_ENDPOINTS[0] || null;
        }
        return endpointByKey.get(selectedKey) || PLATFORM_ENDPOINTS[0] || null;
    }

    function fillEndpointConsole(spec) {
        if (!spec) {
            return;
        }
        const select = ui.byId("platform-endpoint-select");
        if (select) {
            select.value = spec.key;
        }
        setJsonField("platform-endpoint-path-params", spec.pathParams);
        setJsonField("platform-endpoint-query-params", spec.query);
        setJsonField("platform-endpoint-body", spec.body);
        setJsonField("platform-endpoint-headers", {});

        const tokenInput = ui.byId("platform-endpoint-token");
        if (tokenInput && !tokenInput.value) {
            if (spec.auth === "bearer") {
                tokenInput.placeholder = "留空则自动使用共享会话 access token";
            } else if (spec.auth === "admin-bearer") {
                tokenInput.placeholder = "留空则自动使用已保存的管理 Bearer Token";
            } else if (spec.auth === "optional") {
                tokenInput.placeholder = "可选：只在需要时填写 Bearer Token";
            } else {
                tokenInput.placeholder = "默认不需要 Bearer；如需覆盖可手动填写";
            }
        }
        ui.setStatus("platform-endpoint-console-status", `已选择 ${spec.key}。`, "success");
    }

    function renderPlatformEndpointMatrix() {
        const keyword = ui.readValue("platform-endpoint-filter").toLowerCase();
        const filtered = PLATFORM_ENDPOINTS.filter((spec) => {
            const haystack = [
                spec.method,
                spec.path,
                scopeLabel(spec.path),
                authLabel(spec.auth),
                spec.title,
                spec.notes
            ].join(" ").toLowerCase();
            return !keyword || haystack.includes(keyword);
        });

        const matrixNode = ui.byId("platform-endpoint-matrix");
        if (matrixNode) {
            if (!filtered.length) {
                matrixNode.innerHTML = '<div class="empty-state">没有匹配到端点，请调整筛选关键词。</div>';
            } else {
                const rows = filtered.map((spec) => `
                    <tr>
                        <td><strong>${ui.escapeHtml(spec.method)}</strong></td>
                        <td><code>${ui.escapeHtml(spec.path)}</code></td>
                        <td>${ui.escapeHtml(scopeLabel(spec.path))}</td>
                        <td>${ui.escapeHtml(authLabel(spec.auth))}</td>
                        <td>${ui.escapeHtml(spec.title)}</td>
                        <td><button type="button" class="secondary endpoint-pick" data-key="${ui.escapeHtml(spec.key)}">填入调试台</button></td>
                    </tr>
                `).join("");
                matrixNode.innerHTML = `
                    <table>
                        <thead>
                            <tr>
                                <th>方法</th>
                                <th>路径</th>
                                <th>能力域</th>
                                <th>认证</th>
                                <th>说明</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody>${rows}</tbody>
                    </table>
                `;
            }
        }

        const counts = filtered.reduce((acc, spec) => {
            acc[spec.method] = (acc[spec.method] || 0) + 1;
            return acc;
        }, {});
        const methodSummary = ["GET", "POST", "PUT", "PATCH", "DELETE"]
            .filter((method) => counts[method])
            .map((method) => `${method} ${counts[method]}`)
            .join(" | ");

        const summaryInput = ui.byId("platform-endpoint-summary");
        if (summaryInput) {
            summaryInput.value = `${filtered.length}/${PLATFORM_ENDPOINTS.length} 已显示${methodSummary ? ` | ${methodSummary}` : ""}`;
        }

        if (keyword) {
            ui.setStatus("platform-endpoint-status", `已筛选出 ${filtered.length} 个端点。`, "success");
        } else {
            ui.setStatus("platform-endpoint-status", `当前共 ${PLATFORM_ENDPOINTS.length} 个平台端点。`, "success");
        }
    }

    const searchForm = ui.byId("symbol-search-form");
    if (searchForm) {
        searchForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("search-status", "正在搜索标的...");
            try {
                const params = new URLSearchParams({
                    q: ui.readValue("search-query"),
                    limit: String(ui.readNumber("search-limit", 20))
                });
                const type = ui.readValue("search-type");
                if (type) {
                    params.set("type", type);
                }
                const payload = await ui.requestJson("GET", `${ui.publicApi("/v1/search/symbols")}?${params.toString()}`);
                ui.renderJson("search-output", payload);
                ui.renderSearchTable("search-results", payload.items || []);
                ui.setStatus("search-status", `已加载 ${(payload.items || []).length} 条搜索结果。`, "success");
            } catch (error) {
                ui.setStatus("search-status", error.message, "error");
            }
        });
    }

    const searchResults = ui.byId("search-results");
    if (searchResults) {
        searchResults.addEventListener("click", (event) => {
            const target = event.target;
            if (!(target instanceof HTMLElement) || !target.classList.contains("search-pick")) {
                return;
            }
            const symbol = target.dataset.symbol || "";
            if (ui.byId("platform-watchlist-symbol")) {
                ui.byId("platform-watchlist-symbol").value = symbol;
            }
            if (ui.byId("app-trade-id") && !ui.byId("app-trade-id").value) {
                ui.byId("app-trade-id").value = symbol;
            }
            ui.setStatus("platform-watchlist-status", `已将 ${symbol} 填入观察列表表单。`, "success");
        });
    }

    const showPlatformSessionButton = ui.byId("show-platform-session");
    if (showPlatformSessionButton) {
        showPlatformSessionButton.addEventListener("click", () => {
            ui.renderSessionSnapshot("platform-session-output");
            ui.setStatus("platform-session-status", "已显示共享公共会话快照。", "success");
        });
    }

    const clearPlatformSessionButton = ui.byId("clear-platform-session");
    if (clearPlatformSessionButton) {
        clearPlatformSessionButton.addEventListener("click", () => {
            ui.clearPublicSession();
            ui.renderSessionSnapshot("platform-session-output");
            ui.setStatus("platform-session-status", "已清除共享公共会话令牌。", "success");
        });
    }

    function readOptionalPositiveInteger(id, label) {
        const raw = ui.readValue(id);
        if (!raw) {
            return null;
        }
        const value = Number(raw);
        if (!Number.isInteger(value) || value <= 0) {
            throw new Error(`${label} 必须是正整数。`);
        }
        return value;
    }

    function readOptionalBooleanSelect(id) {
        const raw = ui.readValue(id);
        if (raw === "true") {
            return true;
        }
        if (raw === "false") {
            return false;
        }
        return null;
    }

    function parseCommaSeparated(raw) {
        return String(raw || "")
            .split(",")
            .map((value) => value.trim())
            .filter(Boolean);
    }

    function parsePositiveIntegers(raw) {
        return [...new Set(
            parseCommaSeparated(raw)
                .map((value) => Number(value))
                .filter((value) => Number.isInteger(value) && value > 0)
        )];
    }

    function readPlatformWindowHours() {
        return ui.readNumber("platform-strategy-window-hours", 24);
    }

    function syncPlatformAdminFields() {
        const storedAdmin = ui.getAdminStoredUser();
        const email = storedAdmin && storedAdmin.email ? String(storedAdmin.email) : "";
        const authEmail = ui.byId("platform-admin-auth-email");
        const verifyEmail = ui.byId("platform-admin-verify-email");
        const tokenInput = ui.byId("platform-admin-token");
        if (authEmail && !authEmail.value && email) {
            authEmail.value = email;
        }
        if (verifyEmail && !verifyEmail.value && email) {
            verifyEmail.value = email;
        }
        if (tokenInput) {
            tokenInput.value = ui.getAdminToken();
        }
    }

    function setPlatformHtml(id, html) {
        const node = ui.byId(id);
        if (node) {
            node.innerHTML = html;
        }
    }

    function formatMetric(value, digits = 0) {
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) {
            return "--";
        }
        return new Intl.NumberFormat("zh-CN", {
            minimumFractionDigits: digits,
            maximumFractionDigits: digits,
        }).format(numeric);
    }

    function formatPercent(value, digits = 1) {
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) {
            return "--";
        }
        return `${formatMetric(numeric, digits)}%`;
    }

    function formatDateTime(value) {
        if (!value) {
            return "--";
        }
        const parsed = new Date(value);
        if (Number.isNaN(parsed.getTime())) {
            return String(value);
        }
        return parsed.toLocaleString("zh-CN", { hour12: false });
    }

    function metricCard(label, value) {
        return `
            <div class="hero-stat">
                <strong>${ui.escapeHtml(String(value))}</strong>
                <span>${ui.escapeHtml(label)}</span>
            </div>
        `;
    }

    function renderStrategyView(kind, payload) {
        if (!payload) {
            return;
        }
        if (kind === "health") {
            const strategies = Array.isArray(payload.strategies) ? payload.strategies : [];
            const leader = strategies[0] || null;
            const cards = [
                metricCard("策略数量", formatMetric(strategies.length)),
                metricCard("当前第一", leader ? leader.strategy_name : "--"),
                metricCard("最高分", leader ? formatMetric(leader.score, 2) : "--"),
                metricCard("刷新时间", formatDateTime(payload.refreshed_at)),
            ].join("");
            const rows = strategies.map((item) => `
                <tr>
                    <td>${ui.escapeHtml(String(item.rank ?? "--"))}</td>
                    <td><strong>${ui.escapeHtml(item.strategy_name || "--")}</strong></td>
                    <td>${ui.escapeHtml(item.timeframe || "--")}</td>
                    <td>${ui.escapeHtml(formatMetric(item.score, 2))}</td>
                    <td>${ui.escapeHtml(formatMetric(item.degradation, 2))}</td>
                    <td>${ui.escapeHtml(formatMetric(item.symbols_covered || 0))}</td>
                    <td>${ui.escapeHtml(formatMetric(item.signals_generated || 0))}</td>
                    <td>${ui.escapeHtml(item.stable ? "稳定" : "待复核")}</td>
                </tr>
            `).join("");
            setPlatformHtml(
                "platform-strategy-view",
                `
                    <div class="hero-grid">${cards}</div>
                    ${strategies.length ? `
                        <table>
                            <thead>
                                <tr>
                                    <th>排名</th>
                                    <th>策略</th>
                                    <th>周期</th>
                                    <th>得分</th>
                                    <th>退化</th>
                                    <th>覆盖标的</th>
                                    <th>信号数</th>
                                    <th>状态</th>
                                </tr>
                            </thead>
                            <tbody>${rows}</tbody>
                        </table>
                    ` : '<div class="empty-state">当前窗口内还没有策略健康度记录。</div>'}
                `
            );
            return;
        }

        if (kind === "signal-summary") {
            const topSymbols = Array.isArray(payload.top_symbols) ? payload.top_symbols : [];
            const cards = [
                metricCard("信号总数", formatMetric(payload.total_signals || 0)),
                metricCard("待触发", formatMetric(payload.pending_signals || 0)),
                metricCard("平均置信度", formatPercent(payload.avg_confidence || 0, 1)),
                metricCard("平均概率", formatPercent((payload.avg_probability || 0) * 100, 1)),
            ].join("");
            const rows = topSymbols.map((item) => `
                <tr>
                    <td><strong>${ui.escapeHtml(item.symbol || "--")}</strong></td>
                    <td>${ui.escapeHtml(formatMetric(item.count || 0))}</td>
                </tr>
            `).join("");
            setPlatformHtml(
                "platform-strategy-view",
                `
                    <div class="hero-grid">${cards}</div>
                    <div class="split-shell">
                        <div class="table-wrap">
                            <table>
                                <tbody>
                                    <tr><th>生成起点</th><td>${ui.escapeHtml(formatDateTime(payload.generated_after))}</td></tr>
                                    <tr><th>买入信号</th><td>${ui.escapeHtml(formatMetric(payload.buy_signals || 0))}</td></tr>
                                    <tr><th>卖出信号</th><td>${ui.escapeHtml(formatMetric(payload.sell_signals || 0))}</td></tr>
                                    <tr><th>活跃 / 已触发</th><td>${ui.escapeHtml(`${formatMetric(payload.active_signals || 0)} / ${formatMetric(payload.triggered_signals || 0)}`)}</td></tr>
                                </tbody>
                            </table>
                        </div>
                        <div class="table-wrap">
                            ${topSymbols.length ? `
                                <table>
                                    <thead><tr><th>热门标的</th><th>信号数</th></tr></thead>
                                    <tbody>${rows}</tbody>
                                </table>
                            ` : '<div class="empty-state">当前窗口内没有热门标的统计。</div>'}
                        </div>
                    </div>
                `
            );
            return;
        }

        if (kind === "overview") {
            const cards = [
                metricCard("生成信号", formatMetric(payload.generated_signals || 0)),
                metricCard("扫描决策", formatMetric(payload.scanner_decisions || 0)),
                metricCard("通知投递", formatMetric(payload.delivered_notifications || 0)),
                metricCard("交易动作", formatMetric(payload.trade_actions || 0)),
            ].join("");
            setPlatformHtml(
                "platform-strategy-view",
                `
                    <div class="hero-grid">${cards}</div>
                    <table>
                        <tbody>
                            <tr><th>通知请求</th><td>${ui.escapeHtml(formatMetric(payload.notification_requests || 0))}</td></tr>
                            <tr><th>已确认通知</th><td>${ui.escapeHtml(formatMetric(payload.acknowledged_notifications || 0))}</td></tr>
                            <tr><th>启动订阅</th><td>${ui.escapeHtml(formatMetric(payload.subscriptions_started || 0))}</td></tr>
                            <tr><th>TradingAgents 终端</th><td>${ui.escapeHtml(formatMetric(payload.tradingagents_terminals || 0))}</td></tr>
                            <tr><th>最新事件时间</th><td>${ui.escapeHtml(formatDateTime(payload.latest_event_at))}</td></tr>
                        </tbody>
                    </table>
                `
            );
            return;
        }

        if (kind === "backtest-rankings") {
            const rankings = Array.isArray(payload.data) ? payload.data : [];
            const leader = rankings[0] || null;
            const rows = rankings.map((item) => {
                const evidence = item.evidence && typeof item.evidence === "object" ? item.evidence : null;
                const bestWindow = evidence && evidence.best_window_days ? `${evidence.best_window_days}d` : "--";
                const stable = evidence && typeof evidence.stable === "boolean" ? (evidence.stable ? "稳定" : "波动") : "--";
                return `
                    <tr>
                        <td>${ui.escapeHtml(String(item.rank ?? "--"))}</td>
                        <td><strong>${ui.escapeHtml(item.strategy_name || "--")}</strong></td>
                        <td>${ui.escapeHtml(item.timeframe || "--")}</td>
                        <td>${ui.escapeHtml(formatMetric(item.score, 2))}</td>
                        <td>${ui.escapeHtml(formatMetric(item.degradation, 2))}</td>
                        <td>${ui.escapeHtml(formatMetric(item.symbols_covered || 0))}</td>
                        <td>${ui.escapeHtml(bestWindow)}</td>
                        <td>${ui.escapeHtml(stable)}</td>
                    </tr>
                `;
            }).join("");
            const cards = [
                metricCard("排名数量", formatMetric(rankings.length)),
                metricCard("第一策略", leader ? leader.strategy_name : "--"),
                metricCard("最高分", leader ? formatMetric(leader.score, 2) : "--"),
                metricCard("统计时间", formatDateTime(payload.as_of_date)),
            ].join("");
            setPlatformHtml(
                "platform-strategy-view",
                `
                    <div class="hero-grid">${cards}</div>
                    ${rankings.length ? `
                        <table>
                            <thead>
                                <tr>
                                    <th>排名</th>
                                    <th>策略</th>
                                    <th>周期</th>
                                    <th>得分</th>
                                    <th>退化</th>
                                    <th>覆盖标的</th>
                                    <th>最佳窗口</th>
                                    <th>稳定性</th>
                                </tr>
                            </thead>
                            <tbody>${rows}</tbody>
                        </table>
                    ` : '<div class="empty-state">当前还没有回测排名。</div>'}
                `
            );
        }
    }

    function renderScannerView(kind, payload) {
        if (!payload) {
            return;
        }
        if (kind === "observability") {
            const summary = payload.summary || {};
            const runs = Array.isArray(payload.runs) ? payload.runs : [];
            const decisions = Array.isArray(payload.recent_decisions) ? payload.recent_decisions : [];
            const runRows = runs.map((item) => `
                <tr>
                    <td>${ui.escapeHtml(String(item.id ?? "--"))}</td>
                    <td>${ui.escapeHtml(String(item.bucket_id ?? "--"))}</td>
                    <td>${ui.escapeHtml(item.status || "--")}</td>
                    <td>${ui.escapeHtml(`${formatMetric(item.scanned_count || 0)} / ${formatMetric(item.emitted_count || 0)} / ${formatMetric(item.suppressed_count || 0)}`)}</td>
                    <td>${ui.escapeHtml(item.duration_seconds == null ? "--" : `${formatMetric(item.duration_seconds, 3)}s`)}</td>
                    <td>${ui.escapeHtml(formatDateTime(item.started_at))}</td>
                </tr>
            `).join("");
            const decisionRows = decisions.map((item) => `
                <tr>
                    <td><strong>${ui.escapeHtml(item.symbol || "--")}</strong></td>
                    <td>${ui.escapeHtml(item.decision || "--")}</td>
                    <td>${ui.escapeHtml(item.signal_type || "--")}</td>
                    <td>${ui.escapeHtml(item.score == null ? "--" : formatMetric(item.score, 1))}</td>
                    <td>${ui.escapeHtml(item.reason || "--")}</td>
                </tr>
            `).join("");
            setPlatformHtml(
                "platform-scanner-view",
                `
                    <div class="hero-grid">
                        ${metricCard("总运行", formatMetric(summary.total_runs || 0))}
                        ${metricCard("已完成", formatMetric(summary.completed_runs || 0))}
                        ${metricCard("总决策", formatMetric(summary.total_decisions || 0))}
                        ${metricCard("已发出", formatMetric(summary.emitted_decisions || 0))}
                    </div>
                    <div class="split-shell">
                        <div class="table-wrap">
                            ${runs.length ? `
                                <table>
                                    <thead><tr><th>运行 ID</th><th>分桶</th><th>状态</th><th>扫描/发出/抑制</th><th>耗时</th><th>开始时间</th></tr></thead>
                                    <tbody>${runRows}</tbody>
                                </table>
                            ` : '<div class="empty-state">当前筛选条件下没有 scanner 运行。</div>'}
                        </div>
                        <div class="table-wrap">
                            ${decisions.length ? `
                                <table>
                                    <thead><tr><th>代码</th><th>决策</th><th>信号</th><th>分数</th><th>原因</th></tr></thead>
                                    <tbody>${decisionRows}</tbody>
                                </table>
                            ` : '<div class="empty-state">当前筛选条件下没有最近决策。</div>'}
                        </div>
                    </div>
                `
            );
            return;
        }

        if (kind === "live") {
            const decisions = Array.isArray(payload.data) ? payload.data : [];
            const rows = decisions.map((item) => `
                <tr>
                    <td>${ui.escapeHtml(String(item.id ?? "--"))}</td>
                    <td><strong>${ui.escapeHtml(item.symbol || "--")}</strong></td>
                    <td>${ui.escapeHtml(item.decision || "--")}</td>
                    <td>${ui.escapeHtml(item.signal_type || "--")}</td>
                    <td>${ui.escapeHtml(item.score == null ? "--" : formatMetric(item.score, 1))}</td>
                    <td>${ui.escapeHtml(item.suppressed ? "是" : "否")}</td>
                    <td>${ui.escapeHtml(item.reason || "--")}</td>
                </tr>
            `).join("");
            setPlatformHtml(
                "platform-scanner-view",
                `
                    <div class="hero-grid">
                        ${metricCard("返回条数", formatMetric(decisions.length))}
                        ${metricCard("总数", formatMetric(payload.total || 0))}
                        ${metricCard("当前偏移", formatMetric(payload.offset || 0))}
                        ${metricCard("更多结果", payload.has_more ? "是" : "否")}
                    </div>
                    ${decisions.length ? `
                        <table>
                            <thead><tr><th>ID</th><th>代码</th><th>决策</th><th>信号</th><th>分数</th><th>已抑制</th><th>原因</th></tr></thead>
                            <tbody>${rows}</tbody>
                        </table>
                    ` : '<div class="empty-state">当前筛选条件下没有实时决策。</div>'}
                `
            );
        }
    }

    function renderBacktestView(kind, payload) {
        if (!payload) {
            return;
        }
        if (kind === "runs") {
            const runs = Array.isArray(payload.data) ? payload.data : [];
            const completed = runs.filter((item) => item.status === "completed").length;
            const failed = runs.filter((item) => item.status === "failed").length;
            const rows = runs.map((item) => {
                const summary = item.summary && typeof item.summary === "object" ? item.summary : null;
                const summaryText = summary
                    ? [
                        summary.ranking_count ? `${summary.ranking_count} 条排名` : null,
                        summary.top_strategy ? `Top ${summary.top_strategy}` : null,
                    ].filter(Boolean).join(" · ")
                    : "--";
                return `
                    <tr>
                        <td>${ui.escapeHtml(String(item.id ?? "--"))}</td>
                        <td><strong>${ui.escapeHtml(item.strategy_name || "--")}</strong></td>
                        <td>${ui.escapeHtml(item.symbol || "*")}</td>
                        <td>${ui.escapeHtml(item.status || "--")}</td>
                        <td>${ui.escapeHtml(`${item.timeframe || "--"} / ${formatMetric(item.window_days || 0)}d`)}</td>
                        <td>${ui.escapeHtml(summaryText || "--")}</td>
                        <td>${ui.escapeHtml(formatDateTime(item.started_at))}</td>
                    </tr>
                `;
            }).join("");
            setPlatformHtml(
                "platform-backtests-view",
                `
                    <div class="hero-grid">
                        ${metricCard("总运行", formatMetric(payload.total || runs.length))}
                        ${metricCard("当前载入", formatMetric(runs.length))}
                        ${metricCard("已完成", formatMetric(completed))}
                        ${metricCard("失败", formatMetric(failed))}
                    </div>
                    ${runs.length ? `
                        <table>
                            <thead><tr><th>ID</th><th>策略</th><th>标的</th><th>状态</th><th>周期 / 窗口</th><th>摘要</th><th>开始时间</th></tr></thead>
                            <tbody>${rows}</tbody>
                        </table>
                    ` : '<div class="empty-state">当前筛选条件下没有回测运行。</div>'}
                `
            );
            return;
        }

        if (kind === "refresh") {
            const rankings = Array.isArray(payload.rankings) ? payload.rankings : [];
            const rows = rankings.map((item) => `
                <tr>
                    <td>${ui.escapeHtml(String(item.rank ?? "--"))}</td>
                    <td><strong>${ui.escapeHtml(item.strategy_name || "--")}</strong></td>
                    <td>${ui.escapeHtml(item.timeframe || "--")}</td>
                    <td>${ui.escapeHtml(formatMetric(item.score, 2))}</td>
                    <td>${ui.escapeHtml(formatMetric(item.degradation, 2))}</td>
                    <td>${ui.escapeHtml(formatMetric(item.symbols_covered || 0))}</td>
                </tr>
            `).join("");
            setPlatformHtml(
                "platform-backtests-view",
                `
                    <div class="hero-grid">
                        ${metricCard("新运行 ID", formatMetric(payload.run_id || 0))}
                        ${metricCard("实验名", payload.experiment_name || "--")}
                        ${metricCard("排名数量", formatMetric(payload.ranking_count || rankings.length))}
                        ${metricCard("代码版本", payload.code_version || "--")}
                    </div>
                    ${rankings.length ? `
                        <table>
                            <thead><tr><th>排名</th><th>策略</th><th>周期</th><th>得分</th><th>退化</th><th>覆盖标的</th></tr></thead>
                            <tbody>${rows}</tbody>
                        </table>
                    ` : '<div class="empty-state">回测刷新已触发，但当前返回里没有排名数据。</div>'}
                `
            );
        }
    }

    function currentPlatformAdminToken() {
        const inlineToken = ui.readValue("platform-admin-token");
        return inlineToken || ui.requireAdminToken();
    }

    async function requestProtected(method, path, options = {}) {
        return await ui.requestJson(method, ui.publicApi(path), {
            token: ui.requireAccessToken(),
            body: options.body
        });
    }

    async function requestStrategyAdmin(method, path, options = {}) {
        return await ui.requestJson(method, ui.adminApi(path), {
            token: currentPlatformAdminToken(),
            body: options.body
        });
    }

    async function loadProtectedJson(path, outputId, statusId) {
        ui.setStatus(statusId, "正在加载...");
        try {
            const payload = await requestProtected("GET", path);
            ui.renderJson(outputId, payload);
            ui.setStatus(statusId, "加载成功。", "success");
            return payload;
        } catch (error) {
            ui.setStatus(statusId, error.message, "error");
            return null;
        }
    }

    async function loadStrategyAdminJson(path, outputId, statusId) {
        ui.setStatus(statusId, "正在加载...");
        try {
            const payload = await requestStrategyAdmin("GET", path);
            ui.renderJson(outputId, payload);
            ui.setStatus(statusId, "加载成功。", "success");
            return payload;
        } catch (error) {
            ui.setStatus(statusId, error.message, "error");
            return null;
        }
    }

    const addWatchlistForm = ui.byId("platform-watchlist-form");
    if (addWatchlistForm) {
        addWatchlistForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("platform-watchlist-status", "正在创建观察项...");
            try {
                const payload = await ui.requestJson("POST", ui.publicApi("/v1/watchlist"), {
                    token: ui.requireAccessToken(),
                    body: {
                        symbol: ui.readValue("platform-watchlist-symbol"),
                        min_score: ui.readNumber("platform-watchlist-score", 65),
                        notify: ui.readCheckbox("platform-watchlist-notify")
                    }
                });
                ui.renderJson("platform-watchlist-output", payload);
                ui.setStatus("platform-watchlist-status", `已将 ${payload.symbol || ui.readValue("platform-watchlist-symbol")} 加入观察列表。`, "success");
            } catch (error) {
                ui.setStatus("platform-watchlist-status", error.message, "error");
            }
        });
    }

    const loadPlatformWatchlistButton = ui.byId("platform-load-watchlist");
    if (loadPlatformWatchlistButton) {
        loadPlatformWatchlistButton.addEventListener("click", () => {
            loadProtectedJson("/v1/watchlist", "platform-watchlist-output", "platform-watchlist-status");
        });
    }

    const loadPlatformPortfolioButton = ui.byId("platform-load-portfolio");
    if (loadPlatformPortfolioButton) {
        loadPlatformPortfolioButton.addEventListener("click", () => {
            loadProtectedJson("/v1/portfolio", "platform-portfolio-output", "platform-portfolio-status");
        });
    }

    const addPlatformPortfolioForm = ui.byId("platform-portfolio-form");
    if (addPlatformPortfolioForm) {
        addPlatformPortfolioForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("platform-portfolio-status", "正在新增持仓...");
            try {
                const body = {
                    symbol: ui.readValue("platform-portfolio-symbol"),
                    shares: ui.readNumber("platform-portfolio-shares", 1),
                    avg_cost: ui.readNumber("platform-portfolio-avg-cost", 1),
                    target_profit: ui.readNumber("platform-portfolio-target", 0.15),
                    stop_loss: ui.readNumber("platform-portfolio-stop", 0.08),
                    notify: ui.readCheckbox("platform-portfolio-notify")
                };
                const notes = ui.readValue("platform-portfolio-notes");
                if (notes) {
                    body.notes = notes;
                }
                const payload = await ui.requestJson("POST", ui.publicApi("/v1/portfolio"), {
                    token: ui.requireAccessToken(),
                    body
                });
                ui.renderJson("platform-portfolio-output", payload);
                ui.setStatus("platform-portfolio-status", `已新增 ${payload.symbol || body.symbol} 持仓。`, "success");
            } catch (error) {
                ui.setStatus("platform-portfolio-status", error.message, "error");
            }
        });
    }

    const updatePlatformWatchlistForm = ui.byId("platform-update-watchlist-form");
    if (updatePlatformWatchlistForm) {
        updatePlatformWatchlistForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("platform-maintenance-status", "正在更新观察项...");
            try {
                const itemId = readOptionalPositiveInteger("platform-watchlist-item-id", "观察项 ID");
                const body = {};
                const scoreRaw = ui.readValue("platform-watchlist-update-score");
                const notify = readOptionalBooleanSelect("platform-watchlist-update-notify");
                if (scoreRaw) body.min_score = ui.readNumber("platform-watchlist-update-score", 65);
                if (notify !== null) body.notify = notify;
                if (Object.keys(body).length === 0) {
                    throw new Error("提交前至少填写一项观察列表变更。");
                }
                const payload = await requestProtected("PUT", `/v1/watchlist/${itemId}`, { body });
                ui.renderJson("platform-maintenance-output", payload);
                ui.setStatus("platform-maintenance-status", "观察项已更新。", "success");
            } catch (error) {
                ui.setStatus("platform-maintenance-status", error.message, "error");
            }
        });
    }

    const deletePlatformWatchlistButton = ui.byId("platform-delete-watchlist-item");
    if (deletePlatformWatchlistButton) {
        deletePlatformWatchlistButton.addEventListener("click", async () => {
            ui.setStatus("platform-maintenance-status", "正在删除观察项...");
            try {
                const itemId = readOptionalPositiveInteger("platform-watchlist-item-id", "观察项 ID");
                await requestProtected("DELETE", `/v1/watchlist/${itemId}`);
                ui.renderJson("platform-maintenance-output", { message: `已删除观察项 ${itemId}。` });
                ui.setStatus("platform-maintenance-status", "观察项已删除。", "success");
            } catch (error) {
                ui.setStatus("platform-maintenance-status", error.message, "error");
            }
        });
    }

    const updatePlatformPortfolioForm = ui.byId("platform-update-portfolio-form");
    if (updatePlatformPortfolioForm) {
        updatePlatformPortfolioForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("platform-maintenance-status", "正在更新持仓...");
            try {
                const itemId = readOptionalPositiveInteger("platform-portfolio-item-id", "持仓条目 ID");
                const body = {};
                const sharesRaw = ui.readValue("platform-portfolio-update-shares");
                const avgCostRaw = ui.readValue("platform-portfolio-update-cost");
                const targetRaw = ui.readValue("platform-portfolio-update-target");
                const stopRaw = ui.readValue("platform-portfolio-update-stop");
                const notify = readOptionalBooleanSelect("platform-portfolio-update-notify");
                const notes = ui.readValue("platform-portfolio-update-notes");
                if (sharesRaw) body.shares = ui.readNumber("platform-portfolio-update-shares", 1);
                if (avgCostRaw) body.avg_cost = ui.readNumber("platform-portfolio-update-cost", 1);
                if (targetRaw) body.target_profit = ui.readNumber("platform-portfolio-update-target", 0.15);
                if (stopRaw) body.stop_loss = ui.readNumber("platform-portfolio-update-stop", 0.08);
                if (notify !== null) body.notify = notify;
                if (notes) body.notes = notes;
                if (Object.keys(body).length === 0) {
                    throw new Error("提交前至少填写一项持仓变更。");
                }
                const payload = await requestProtected("PUT", `/v1/portfolio/${itemId}`, { body });
                ui.renderJson("platform-maintenance-output", payload);
                ui.setStatus("platform-maintenance-status", "持仓已更新。", "success");
            } catch (error) {
                ui.setStatus("platform-maintenance-status", error.message, "error");
            }
        });
    }

    const deletePlatformPortfolioButton = ui.byId("platform-delete-portfolio-item");
    if (deletePlatformPortfolioButton) {
        deletePlatformPortfolioButton.addEventListener("click", async () => {
            ui.setStatus("platform-maintenance-status", "正在删除持仓...");
            try {
                const itemId = readOptionalPositiveInteger("platform-portfolio-item-id", "持仓条目 ID");
                await requestProtected("DELETE", `/v1/portfolio/${itemId}`);
                ui.renderJson("platform-maintenance-output", { message: `已删除持仓条目 ${itemId}。` });
                ui.setStatus("platform-maintenance-status", "持仓已删除。", "success");
            } catch (error) {
                ui.setStatus("platform-maintenance-status", error.message, "error");
            }
        });
    }

    const appTradeForm = ui.byId("app-trade-form");
    if (appTradeForm) {
        appTradeForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("trade-status", "正在加载已登录交易信息...");
            try {
                const tradeId = ui.readValue("app-trade-id");
                const payload = await requestProtected("GET", `/v1/trades/${encodeURIComponent(tradeId)}/app-info`);
                ui.renderJson("trade-output", payload);
                ui.setStatus("trade-status", `已加载 ${tradeId} 的应用交易信息。`, "success");
            } catch (error) {
                ui.setStatus("trade-status", error.message, "error");
            }
        });
    }

    const appConfirmTradeButton = ui.byId("app-confirm-trade");
    if (appConfirmTradeButton) {
        appConfirmTradeButton.addEventListener("click", async () => {
            ui.setStatus("trade-status", "正在确认已登录交易...");
            try {
                const tradeId = ui.readValue("app-trade-id");
                const payload = await requestProtected("POST", `/v1/trades/${encodeURIComponent(tradeId)}/app-confirm`);
                ui.renderJson("trade-output", payload);
                ui.setStatus("trade-status", payload.message || "交易已确认。", "success");
            } catch (error) {
                ui.setStatus("trade-status", error.message, "error");
            }
        });
    }

    const appIgnoreTradeButton = ui.byId("app-ignore-trade");
    if (appIgnoreTradeButton) {
        appIgnoreTradeButton.addEventListener("click", async () => {
            ui.setStatus("trade-status", "正在忽略已登录交易...");
            try {
                const tradeId = ui.readValue("app-trade-id");
                const payload = await requestProtected("POST", `/v1/trades/${encodeURIComponent(tradeId)}/app-ignore`);
                ui.renderJson("trade-output", payload);
                ui.setStatus("trade-status", payload.message || "交易已忽略。", "success");
            } catch (error) {
                ui.setStatus("trade-status", error.message, "error");
            }
        });
    }

    const appAdjustTradeButton = ui.byId("app-adjust-trade");
    if (appAdjustTradeButton) {
        appAdjustTradeButton.addEventListener("click", async () => {
            ui.setStatus("trade-status", "正在记录已登录交易调整...");
            try {
                const tradeId = ui.readValue("app-trade-id");
                const payload = await requestProtected("POST", `/v1/trades/${encodeURIComponent(tradeId)}/app-adjust`, {
                    body: {
                        actual_shares: ui.readNumber("app-adjust-shares", 1),
                        actual_price: ui.readNumber("app-adjust-price", 1)
                    }
                });
                ui.renderJson("trade-output", payload);
                ui.setStatus("trade-status", payload.message || "交易调整已记录。", "success");
            } catch (error) {
                ui.setStatus("trade-status", error.message, "error");
            }
        });
    }

    const publicTradeForm = ui.byId("public-trade-form");
    if (publicTradeForm) {
        publicTradeForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("trade-status", "正在加载公开交易信息...");
            try {
                const tradeId = ui.readValue("public-trade-id");
                const token = ui.readValue("public-trade-token");
                const params = new URLSearchParams({ t: token });
                const payload = await ui.requestJson(
                    "GET",
                    `${ui.publicApi(`/v1/trades/${encodeURIComponent(tradeId)}/info`)}?${params.toString()}`
                );
                ui.renderJson("trade-output", payload);
                ui.setStatus("trade-status", `已加载 ${tradeId} 的公开交易信息。`, "success");
            } catch (error) {
                ui.setStatus("trade-status", error.message, "error");
            }
        });
    }

    const publicConfirmTradeButton = ui.byId("public-confirm-trade");
    if (publicConfirmTradeButton) {
        publicConfirmTradeButton.addEventListener("click", async () => {
            ui.setStatus("trade-status", "正在通过公开链接确认交易...");
            try {
                const tradeId = ui.readValue("public-trade-id");
                const token = ui.readValue("public-trade-token");
                const params = new URLSearchParams({ action: "accept", t: token });
                const payload = await ui.requestJson(
                    "POST",
                    `${ui.publicApi(`/v1/trades/${encodeURIComponent(tradeId)}/confirm`)}?${params.toString()}`
                );
                ui.renderJson("trade-output", payload);
                ui.setStatus("trade-status", payload.message || "公开交易已确认。", "success");
            } catch (error) {
                ui.setStatus("trade-status", error.message, "error");
            }
        });
    }

    const publicIgnoreTradeButton = ui.byId("public-ignore-trade");
    if (publicIgnoreTradeButton) {
        publicIgnoreTradeButton.addEventListener("click", async () => {
            ui.setStatus("trade-status", "正在通过公开链接忽略交易...");
            try {
                const tradeId = ui.readValue("public-trade-id");
                const token = ui.readValue("public-trade-token");
                const params = new URLSearchParams({ t: token });
                const payload = await ui.requestJson(
                    "POST",
                    `${ui.publicApi(`/v1/trades/${encodeURIComponent(tradeId)}/ignore`)}?${params.toString()}`
                );
                ui.renderJson("trade-output", payload);
                ui.setStatus("trade-status", payload.message || "公开交易已忽略。", "success");
            } catch (error) {
                ui.setStatus("trade-status", error.message, "error");
            }
        });
    }

    const publicAdjustTradeButton = ui.byId("public-adjust-trade");
    if (publicAdjustTradeButton) {
        publicAdjustTradeButton.addEventListener("click", async () => {
            ui.setStatus("trade-status", "正在通过公开链接记录调整...");
            try {
                const tradeId = ui.readValue("public-trade-id");
                const token = ui.readValue("public-trade-token");
                const params = new URLSearchParams({ t: token });
                const payload = await ui.requestJson(
                    "POST",
                    `${ui.publicApi(`/v1/trades/${encodeURIComponent(tradeId)}/adjust`)}?${params.toString()}`,
                    {
                        body: {
                            actual_shares: ui.readNumber("public-adjust-shares", 1),
                            actual_price: ui.readNumber("public-adjust-price", 1)
                        }
                    }
                );
                ui.renderJson("trade-output", payload);
                ui.setStatus("trade-status", payload.message || "公开交易调整已记录。", "success");
            } catch (error) {
                ui.setStatus("trade-status", error.message, "error");
            }
        });
    }

    syncPlatformAdminFields();

    const platformAdminSendCodeForm = ui.byId("platform-admin-send-code-form");
    if (platformAdminSendCodeForm) {
        platformAdminSendCodeForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("platform-admin-token-status", "正在发送管理验证码...");
            try {
                const payload = await ui.requestJson("POST", ui.publicApi("/v1/admin-auth/send-code"), {
                    body: { email: ui.readValue("platform-admin-auth-email") }
                });
                if (ui.byId("platform-admin-verify-email")) {
                    ui.byId("platform-admin-verify-email").value = ui.readValue("platform-admin-auth-email");
                }
                ui.renderJson("platform-admin-session-output", payload);
                ui.setStatus("platform-admin-token-status", payload.message || "管理验证码已发送。", "success");
            } catch (error) {
                ui.setStatus("platform-admin-token-status", error.message, "error");
            }
        });
    }

    const platformAdminVerifyForm = ui.byId("platform-admin-verify-form");
    if (platformAdminVerifyForm) {
        platformAdminVerifyForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("platform-admin-token-status", "正在验证管理验证码...");
            try {
                const payload = await ui.requestJson("POST", ui.publicApi("/v1/admin-auth/verify"), {
                    body: {
                        email: ui.readValue("platform-admin-verify-email"),
                        code: ui.readValue("platform-admin-verify-code"),
                        locale: ui.readValue("platform-admin-verify-locale"),
                        timezone: ui.readValue("platform-admin-verify-timezone")
                    }
                });
                ui.setAdminSession(payload);
                syncPlatformAdminFields();
                ui.renderSessionSnapshot("platform-admin-session-output");
                ui.setStatus("platform-admin-token-status", "策略权限会话已保存。", "success");
            } catch (error) {
                ui.setStatus("platform-admin-token-status", error.message, "error");
            }
        });
    }

    const refreshPlatformAdminSessionButton = ui.byId("platform-refresh-admin-session");
    if (refreshPlatformAdminSessionButton) {
        refreshPlatformAdminSessionButton.addEventListener("click", async () => {
            ui.setStatus("platform-admin-token-status", "正在刷新策略会话...");
            try {
                const refreshToken = ui.getAdminRefreshToken();
                if (!refreshToken) {
                    throw new Error("请先完成管理员验证码验证，或提供可用的刷新令牌。");
                }
                const payload = await ui.requestJson("POST", ui.publicApi("/v1/admin-auth/refresh"), {
                    body: { refresh_token: refreshToken }
                });
                ui.setAdminSession(payload);
                syncPlatformAdminFields();
                ui.renderSessionSnapshot("platform-admin-session-output");
                ui.setStatus("platform-admin-token-status", "策略权限会话已刷新。", "success");
            } catch (error) {
                ui.setStatus("platform-admin-token-status", error.message, "error");
            }
        });
    }

    const savePlatformAdminTokenButton = ui.byId("platform-save-admin-token");
    if (savePlatformAdminTokenButton) {
        savePlatformAdminTokenButton.addEventListener("click", () => {
            ui.clearAdminSession();
            const token = ui.setAdminToken(ui.readValue("platform-admin-token"));
            ui.renderSessionSnapshot("platform-admin-session-output");
            ui.setStatus(
                "platform-admin-token-status",
                token ? "策略权限令牌已保存。" : "已清空策略权限令牌。",
                token ? "success" : "info"
            );
        });
    }

    const showPlatformAdminSessionButton = ui.byId("platform-show-admin-session");
    if (showPlatformAdminSessionButton) {
        showPlatformAdminSessionButton.addEventListener("click", () => {
            ui.renderSessionSnapshot("platform-admin-session-output");
            ui.setStatus("platform-admin-token-status", "已显示当前策略权限状态。", "success");
        });
    }

    const clearPlatformAdminTokenButton = ui.byId("platform-clear-admin-token");
    if (clearPlatformAdminTokenButton) {
        clearPlatformAdminTokenButton.addEventListener("click", () => {
            ui.clearAdminSession();
            syncPlatformAdminFields();
            ui.renderSessionSnapshot("platform-admin-session-output");
            ui.setStatus("platform-admin-token-status", "已清除策略权限会话。", "success");
        });
    }

    const loadPlatformStrategyHealthButton = ui.byId("platform-load-strategy-health");
    if (loadPlatformStrategyHealthButton) {
        loadPlatformStrategyHealthButton.addEventListener("click", async () => {
            const payload = await loadStrategyAdminJson(
                `/v1/admin/analytics/strategy-health?window_hours=${readPlatformWindowHours()}`,
                "platform-strategy-output",
                "platform-strategy-status"
            );
            if (payload) {
                renderStrategyView("health", payload);
            } else {
                setPlatformHtml("platform-strategy-view", '<div class="empty-state">策略健康度加载失败，请确认高权限策略凭证有效后重试。</div>');
            }
        });
    }

    const loadPlatformSignalSummaryButton = ui.byId("platform-load-signal-summary");
    if (loadPlatformSignalSummaryButton) {
        loadPlatformSignalSummaryButton.addEventListener("click", async () => {
            const payload = await loadStrategyAdminJson(
                `/v1/admin/signal-stats/summary?window_hours=${readPlatformWindowHours()}`,
                "platform-strategy-output",
                "platform-strategy-status"
            );
            if (payload) {
                renderStrategyView("signal-summary", payload);
            } else {
                setPlatformHtml("platform-strategy-view", '<div class="empty-state">信号摘要加载失败，请检查策略会话或筛选参数。</div>');
            }
        });
    }

    const loadPlatformAnalyticsOverviewButton = ui.byId("platform-load-analytics-overview");
    if (loadPlatformAnalyticsOverviewButton) {
        loadPlatformAnalyticsOverviewButton.addEventListener("click", async () => {
            const payload = await loadStrategyAdminJson(
                `/v1/admin/analytics/overview?window_hours=${readPlatformWindowHours()}`,
                "platform-strategy-output",
                "platform-strategy-status"
            );
            if (payload) {
                renderStrategyView("overview", payload);
            } else {
                setPlatformHtml("platform-strategy-view", '<div class="empty-state">策略总览加载失败，请确认管理员会话仍然有效。</div>');
            }
        });
    }

    const loadPlatformBacktestRankingsButton = ui.byId("platform-load-backtest-rankings");
    if (loadPlatformBacktestRankingsButton) {
        loadPlatformBacktestRankingsButton.addEventListener("click", async () => {
            const query = buildQueryString({
                timeframe: ui.readValue("platform-backtests-rankings-timeframe") || "1d",
                limit: ui.readNumber("platform-backtests-rankings-limit", 20)
            });
            const payload = await loadStrategyAdminJson(
                `/v1/admin/backtests/rankings/latest${query ? `?${query}` : ""}`,
                "platform-strategy-output",
                "platform-strategy-status"
            );
            if (payload) {
                renderStrategyView("backtest-rankings", payload);
            } else {
                setPlatformHtml("platform-strategy-view", '<div class="empty-state">回测排名加载失败，请稍后重试或检查回测服务状态。</div>');
            }
        });
    }

    const loadPlatformScannerObservabilityButton = ui.byId("platform-load-scanner-observability");
    if (loadPlatformScannerObservabilityButton) {
        loadPlatformScannerObservabilityButton.addEventListener("click", async () => {
            try {
                const query = buildQueryString({
                    status: ui.readValue("platform-scanner-status"),
                    bucket_id: readOptionalPositiveInteger("platform-scanner-bucket-id", "扫描器分桶 ID"),
                    symbol: ui.readValue("platform-scanner-symbol"),
                    decision: ui.readValue("platform-scanner-decision"),
                    limit: ui.readNumber("platform-scanner-limit", 25),
                    decision_limit: ui.readNumber("platform-scanner-decision-limit", 25)
                });
                const payload = await loadStrategyAdminJson(
                    `/v1/admin/scanner/observability${query ? `?${query}` : ""}`,
                    "platform-scanner-output",
                    "platform-scanner-status-output"
                );
                if (payload) {
                    renderScannerView("observability", payload);
                } else {
                    setPlatformHtml("platform-scanner-view", '<div class="empty-state">扫描器总览加载失败，请确认策略权限和查询条件。</div>');
                }
            } catch (error) {
                setPlatformHtml("platform-scanner-view", '<div class="empty-state">扫描器参数校验失败，请修正查询条件后重试。</div>');
                ui.setStatus("platform-scanner-status-output", error.message, "error");
            }
        });
    }

    const loadPlatformScannerLiveDecisionsButton = ui.byId("platform-load-scanner-live-decisions");
    if (loadPlatformScannerLiveDecisionsButton) {
        loadPlatformScannerLiveDecisionsButton.addEventListener("click", async () => {
            const query = buildQueryString({
                symbol: ui.readValue("platform-scanner-symbol"),
                decision: ui.readValue("platform-scanner-decision"),
                limit: ui.readNumber("platform-scanner-decision-limit", 25)
            });
            const payload = await loadStrategyAdminJson(
                `/v1/admin/scanner/live-decision${query ? `?${query}` : ""}`,
                "platform-scanner-output",
                "platform-scanner-status-output"
            );
            if (payload) {
                renderScannerView("live", payload);
            } else {
                setPlatformHtml("platform-scanner-view", '<div class="empty-state">实时决策加载失败，请检查筛选条件或管理员会话。</div>');
            }
        });
    }

    const loadPlatformBacktestRunsButton = ui.byId("platform-load-backtest-runs");
    if (loadPlatformBacktestRunsButton) {
        loadPlatformBacktestRunsButton.addEventListener("click", async () => {
            const query = buildQueryString({
                status: ui.readValue("platform-backtests-status"),
                strategy_name: ui.readValue("platform-backtests-strategy"),
                timeframe: ui.readValue("platform-backtests-timeframe") || "1d",
                symbol: ui.readValue("platform-backtests-symbol"),
                limit: ui.readNumber("platform-backtests-limit", 25)
            });
            const payload = await loadStrategyAdminJson(
                `/v1/admin/backtests/runs${query ? `?${query}` : ""}`,
                "platform-backtests-output",
                "platform-backtests-status-output"
            );
            if (payload) {
                renderBacktestView("runs", payload);
            } else {
                setPlatformHtml("platform-backtests-view", '<div class="empty-state">回测运行加载失败，请确认回测接口可用。</div>');
            }
        });
    }

    const triggerPlatformBacktestRefreshButton = ui.byId("platform-trigger-backtest-refresh");
    if (triggerPlatformBacktestRefreshButton) {
        triggerPlatformBacktestRefreshButton.addEventListener("click", async () => {
            const confirmInput = ui.byId("platform-backtests-refresh-confirm");
            const isConfirmed = confirmInput instanceof HTMLInputElement ? confirmInput.checked : false;
            if (!isConfirmed) {
                ui.setStatus("platform-backtests-status-output", "请先勾选高权限确认，再触发回测排名刷新。", "error");
                return;
            }
            try {
                const symbols = parseCommaSeparated(ui.readValue("platform-backtests-refresh-symbols"));
                const strategyNames = parseCommaSeparated(ui.readValue("platform-backtests-refresh-strategies"));
                const windows = parsePositiveIntegers(ui.readValue("platform-backtests-refresh-windows"));
                const timeframe = ui.readValue("platform-backtests-timeframe") || "1d";
                const scopeSummary = [
                    `周期：${timeframe}`,
                    `标的：${symbols.length ? symbols.join(", ") : "全部"}`,
                    `策略：${strategyNames.length ? strategyNames.join(", ") : "全部"}`,
                    `窗口：${windows.length ? windows.join(", ") : "默认"}`,
                ].join("\n");
                if (!window.confirm(`即将触发高权限回测刷新：\n${scopeSummary}\n\n请确认这些范围无误。`)) {
                    ui.setStatus("platform-backtests-status-output", "已取消回测刷新。", "info");
                    return;
                }
                triggerPlatformBacktestRefreshButton.disabled = true;
                ui.setStatus("platform-backtests-status-output", "正在触发回测刷新...");
                const payload = await requestStrategyAdmin("POST", "/v1/admin/backtests/runs", {
                    body: {
                        symbols: symbols.length > 0 ? symbols : null,
                        strategy_names: strategyNames.length > 0 ? strategyNames : null,
                        windows: windows.length > 0 ? windows : null,
                        timeframe,
                    }
                });
                ui.renderJson("platform-backtests-output", payload);
                renderBacktestView("refresh", payload);
                ui.setStatus("platform-backtests-status-output", "已触发回测刷新。", "success");
                if (confirmInput instanceof HTMLInputElement) {
                    confirmInput.checked = false;
                }
            } catch (error) {
                setPlatformHtml("platform-backtests-view", '<div class="empty-state">回测刷新触发失败，请检查策略凭证和输入参数。</div>');
                ui.setStatus("platform-backtests-status-output", error.message, "error");
            } finally {
                triggerPlatformBacktestRefreshButton.disabled = false;
            }
        });
    }

    const endpointFilterInput = ui.byId("platform-endpoint-filter");
    if (endpointFilterInput) {
        endpointFilterInput.addEventListener("input", () => {
            renderPlatformEndpointMatrix();
        });
    }

    const endpointMatrix = ui.byId("platform-endpoint-matrix");
    if (endpointMatrix) {
        endpointMatrix.addEventListener("click", (event) => {
            const target = event.target;
            if (!(target instanceof HTMLElement) || !target.classList.contains("endpoint-pick")) {
                return;
            }
            const key = target.dataset.key || "";
            const spec = endpointByKey.get(key);
            if (!spec) {
                return;
            }
            fillEndpointConsole(spec);
        });
    }

    const endpointSelect = ui.byId("platform-endpoint-select");
    if (endpointSelect) {
        endpointSelect.addEventListener("change", () => {
            fillEndpointConsole(currentEndpointSpec());
        });
    }

    const endpointConsoleForm = ui.byId("platform-endpoint-console-form");
    if (endpointConsoleForm) {
        endpointConsoleForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            const spec = currentEndpointSpec();
            if (!spec) {
                return;
            }
            ui.setStatus("platform-endpoint-console-status", `正在请求 ${spec.key} ...`);
            try {
                const pathParams = parseJsonObjectInput("platform-endpoint-path-params", "路径参数");
                const queryParams = parseJsonObjectInput("platform-endpoint-query-params", "查询参数");
                const headers = parseJsonObjectInput("platform-endpoint-headers", "附加请求头");
                const body = parseJsonInput("platform-endpoint-body", "请求体");

                const resolvedPath = applyPathParams(spec.path, pathParams);
                const queryString = buildQueryString(queryParams);
                const requestBase = spec.base === "admin"
                    ? ui.adminApi(resolvedPath)
                    : ui.publicApi(resolvedPath);
                const url = queryString
                    ? `${requestBase}?${queryString}`
                    : requestBase;

                const manualToken = ui.readValue("platform-endpoint-token");
                const requestOptions = { headers };
                if (spec.auth === "bearer") {
                    requestOptions.token = manualToken || ui.requireAccessToken();
                } else if (spec.auth === "admin-bearer") {
                    requestOptions.token = manualToken || currentPlatformAdminToken();
                } else if (manualToken) {
                    requestOptions.token = manualToken;
                }
                if (body !== null) {
                    requestOptions.body = body;
                }

                const payload = await ui.requestJson(spec.method, url, requestOptions);
                ui.renderJson(
                    "platform-endpoint-output",
                    payload === null ? { message: "请求成功（无响应体）。" } : payload
                );
                ui.setStatus("platform-endpoint-console-status", `${spec.key} 请求成功。`, "success");
            } catch (error) {
                ui.setStatus("platform-endpoint-console-status", error.message, "error");
            }
        });
    }

    const resetEndpointConsoleButton = ui.byId("platform-endpoint-reset");
    if (resetEndpointConsoleButton) {
        resetEndpointConsoleButton.addEventListener("click", () => {
            const first = PLATFORM_ENDPOINTS[0] || null;
            if (first) {
                fillEndpointConsole(first);
            }
            const tokenInput = ui.byId("platform-endpoint-token");
            if (tokenInput) {
                tokenInput.value = "";
            }
            ui.renderJson("platform-endpoint-output", "");
            ui.setStatus("platform-endpoint-console-status", "调试台已重置。", "success");
        });
    }

    populatePlatformEndpointSelect();
    renderPlatformEndpointMatrix();
    fillEndpointConsole(currentEndpointSpec());

    ui.renderSessionSnapshot("platform-session-output");
    ui.renderSessionSnapshot("platform-admin-session-output");
});
"""

_ADMIN_SCRIPT = """
window.addEventListener("DOMContentLoaded", () => {
    const ui = window.stockPyUi;

    function syncAdminSessionFields() {
        if (ui.byId("admin-token")) {
            ui.byId("admin-token").value = ui.getAdminToken();
        }
        if (ui.byId("admin-operator-id")) {
            ui.byId("admin-operator-id").value = ui.getAdminOperatorId();
        }
    }

    function parseCommaSeparated(raw) {
        return String(raw || "")
            .split(",")
            .map((value) => value.trim())
            .filter(Boolean);
    }

    function parsePositiveIntegers(raw) {
        return [...new Set(
            parseCommaSeparated(raw)
                .map((value) => Number(value))
                .filter((value) => Number.isInteger(value) && value > 0)
        )];
    }

    function parsePositiveNumberList(raw, label) {
        return [...new Set(
            parseCommaSeparated(raw)
                .map((value) => Number(value))
                .filter((value) => Number.isFinite(value) && value > 0)
        )];
    }

    function readOptionalPositiveInteger(id, label) {
        const raw = ui.readValue(id);
        if (!raw) {
            return null;
        }
        const value = Number(raw);
        if (!Number.isInteger(value) || value <= 0) {
            throw new Error(`${label} 必须是正整数。`);
        }
        return value;
    }

    function readOptionalBooleanSelect(id) {
        const raw = ui.readValue(id);
        if (raw === "true") {
            return true;
        }
        if (raw === "false") {
            return false;
        }
        return null;
    }

    function buildQueryString(entries) {
        const params = new URLSearchParams();
        for (const [key, value] of entries) {
            if (value !== null && value !== undefined && value !== "") {
                params.set(key, String(value));
            }
        }
        return params.toString();
    }

    function parseOptionalJson(raw, label) {
        if (!String(raw || "").trim()) {
            return null;
        }
        try {
            return JSON.parse(raw);
        } catch (_error) {
            throw new Error(`${label} 必须是有效 JSON。`);
        }
    }

    syncAdminSessionFields();
    if (ui.byId("admin-verify-timezone") && !ui.byId("admin-verify-timezone").value) {
        ui.byId("admin-verify-timezone").value = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
    }

    const sendCodeForm = ui.byId("admin-send-code-form");
    if (sendCodeForm) {
        sendCodeForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("admin-auth-status", "正在发送管理验证码...");
            try {
                const payload = await ui.requestJson("POST", ui.publicApi("/v1/admin-auth/send-code"), {
                    body: { email: ui.readValue("admin-auth-email") }
                });
                if (payload && payload.dev_code && ui.byId("admin-verify-code")) {
                    ui.byId("admin-verify-code").value = payload.dev_code;
                }
                if (ui.byId("admin-verify-email")) {
                    ui.byId("admin-verify-email").value = ui.readValue("admin-auth-email");
                }
                ui.renderJson("admin-auth-output", payload);
                ui.setStatus("admin-auth-status", payload.message || "管理验证码已发送。", "success");
            } catch (error) {
                ui.setStatus("admin-auth-status", error.message, "error");
            }
        });
    }

    const verifyForm = ui.byId("admin-verify-form");
    if (verifyForm) {
        verifyForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("admin-auth-status", "正在验证管理验证码...");
            try {
                const payload = await ui.requestJson("POST", ui.publicApi("/v1/admin-auth/verify"), {
                    body: {
                        email: ui.readValue("admin-verify-email"),
                        code: ui.readValue("admin-verify-code"),
                        locale: ui.readValue("admin-verify-locale") || null,
                        timezone: ui.readValue("admin-verify-timezone") || null
                    }
                });
                ui.setAdminSession(payload);
                syncAdminSessionFields();
                ui.renderJson("admin-auth-output", payload);
                ui.renderSessionSnapshot("admin-session-output");
                ui.setStatus("admin-auth-status", "管理会话已保存到本地。", "success");
            } catch (error) {
                ui.setStatus("admin-auth-status", error.message, "error");
            }
        });
    }

    const refreshButton = ui.byId("refresh-admin-session");
    if (refreshButton) {
        refreshButton.addEventListener("click", async () => {
            ui.setStatus("admin-auth-status", "正在刷新管理会话...");
            try {
                const payload = await ui.requestJson("POST", ui.publicApi("/v1/admin-auth/refresh"), {
                    body: { refresh_token: ui.getAdminRefreshToken() }
                });
                ui.setAdminSession(payload);
                syncAdminSessionFields();
                ui.renderJson("admin-auth-output", payload);
                ui.renderSessionSnapshot("admin-session-output");
                ui.setStatus("admin-auth-status", "管理会话已刷新。", "success");
            } catch (error) {
                ui.setStatus("admin-auth-status", error.message, "error");
            }
        });
    }

    const logoutButton = ui.byId("logout-admin-session");
    if (logoutButton) {
        logoutButton.addEventListener("click", async () => {
            ui.setStatus("admin-auth-status", "正在退出管理会话...");
            try {
                await ui.requestJson("POST", ui.publicApi("/v1/admin-auth/logout"), {
                    token: ui.requireAdminToken(),
                    body: { refresh_token: ui.getAdminRefreshToken() || null }
                });
                ui.clearAdminSession();
                syncAdminSessionFields();
                ui.renderJson("admin-auth-output", { message: "已成功退出登录" });
                ui.renderSessionSnapshot("admin-session-output");
                ui.setStatus("admin-auth-status", "管理会话已清除。", "success");
            } catch (error) {
                ui.setStatus("admin-auth-status", error.message, "error");
            }
        });
    }

    const saveTokenButton = ui.byId("save-admin-token");
    if (saveTokenButton) {
        saveTokenButton.addEventListener("click", () => {
            ui.clearAdminSession();
            const token = ui.setAdminToken(ui.readValue("admin-token"));
            const operatorId = ui.setAdminOperatorId(ui.readValue("admin-operator-id"));
            syncAdminSessionFields();
            ui.renderSessionSnapshot("admin-session-output");
            const message = token
                ? `已保存手动管理 Bearer Token（${token.length} 个字符）。${operatorId ? `操作员专用路由将使用操作员 ID ${operatorId}。` : ""}`
                : "已清除管理 Bearer Token。";
            ui.setStatus(
                "admin-auth-status",
                message,
                "success"
            );
        });
    }

    const clearTokenButton = ui.byId("clear-admin-session");
    if (clearTokenButton) {
        clearTokenButton.addEventListener("click", () => {
            ui.clearAdminSession();
            syncAdminSessionFields();
            ui.renderSessionSnapshot("admin-session-output");
            ui.setStatus("admin-auth-status", "已清除缓存的管理会话状态。", "success");
        });
    }

    const showAdminSessionButton = ui.byId("show-admin-session");
    if (showAdminSessionButton) {
        showAdminSessionButton.addEventListener("click", () => {
            ui.renderSessionSnapshot("admin-session-output");
            ui.setStatus("admin-session-status", "已显示当前 UI 的接口地址与令牌状态。", "success");
        });
    }

    function readWindowHours() {
        return ui.readNumber("admin-window-hours", 24);
    }

    async function requestAdmin(method, path, options = {}) {
        return await ui.requestJson(method, ui.adminApi(path), {
            token: ui.requireAdminToken(),
            operatorId: options.operatorRequired
                ? ui.requireAdminOperatorId()
                : options.operatorId,
            body: options.body
        });
    }

    async function loadAdminJson(path, outputId, statusId) {
        ui.setStatus(statusId, "正在加载...");
        try {
            const payload = await requestAdmin("GET", path);
            ui.renderJson(outputId, payload);
            ui.setStatus(statusId, "加载成功。", "success");
        } catch (error) {
            ui.setStatus(statusId, error.message, "error");
        }
    }

    const loadOperatorsButton = ui.byId("load-operators");
    if (loadOperatorsButton) {
        loadOperatorsButton.addEventListener("click", () => {
            const params = new URLSearchParams();
            const query = ui.readValue("admin-operators-query");
            const role = ui.readValue("admin-operators-role");
            const isActive = ui.readValue("admin-operators-active");
            if (query) {
                params.set("query", query);
            }
            if (role) {
                params.set("role", role);
            }
            if (isActive) {
                params.set("is_active", isActive);
            }
            params.set("limit", String(ui.readNumber("admin-operators-limit", 25)));
            loadAdminJson(`/v1/admin/operators?${params.toString()}`, "admin-operators-output", "admin-operators-status");
        });
    }

    const upsertOperatorForm = ui.byId("upsert-operator-form");
    if (upsertOperatorForm) {
        upsertOperatorForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("admin-operators-status", "正在保存操作员权限...");
            try {
                const userId = Number(ui.readValue("admin-operator-user-id"));
                if (!Number.isInteger(userId) || userId <= 0) {
                    throw new Error("操作员用户 ID 必须是正整数。");
                }

                const body = {};
                const role = ui.readValue("admin-operator-role");
                const scopes = parseCommaSeparated(ui.readValue("admin-operator-scopes"));
                const activeState = ui.readValue("admin-operator-is-active");

                if (role) {
                    body.role = role;
                }
                if (scopes.length > 0) {
                    body.scopes = scopes;
                }
                if (activeState === "true" || activeState === "false") {
                    body.is_active = activeState === "true";
                }
                if (Object.keys(body).length === 0) {
                    throw new Error("提交前至少填写一项操作员变更。");
                }

                const payload = await ui.requestJson("PUT", ui.adminApi(`/v1/admin/operators/${userId}`), {
                    token: ui.requireAdminToken(),
                    operatorId: ui.getAdminOperatorId() || undefined,
                    body
                });
                ui.renderJson("admin-operators-output", payload);
                ui.setStatus("admin-operators-status", "操作员权限已更新。", "success");
            } catch (error) {
                ui.setStatus("admin-operators-status", error.message, "error");
            }
        });
    }

    const manualDistributionForm = ui.byId("manual-distribution-form");
    if (manualDistributionForm) {
        manualDistributionForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("admin-distribution-status", "正在排入手动分发...");
            try {
                const userIds = parsePositiveIntegers(ui.readValue("distribution-user-ids"));
                if (userIds.length === 0) {
                    throw new Error("至少提供一个目标用户 ID。");
                }

                const channels = [];
                if (ui.readCheckbox("distribution-channel-email")) {
                    channels.push("email");
                }
                if (ui.readCheckbox("distribution-channel-push")) {
                    channels.push("push");
                }
                if (channels.length === 0) {
                    throw new Error("至少选择一个投递渠道。");
                }

                const payload = await ui.requestJson("POST", ui.adminApi("/v1/admin/distribution/manual-message"), {
                    token: ui.requireAdminToken(),
                    operatorId: ui.requireAdminOperatorId(),
                    body: {
                        user_ids: userIds,
                        title: ui.readValue("distribution-title"),
                        body: ui.readValue("distribution-body"),
                        channels,
                        notification_type: ui.readValue("distribution-type") || "manual.message",
                        ack_required: ui.readCheckbox("distribution-ack-required"),
                        ack_deadline_at: ui.readValue("distribution-ack-deadline") || null,
                        metadata: parseOptionalJson(ui.readValue("distribution-metadata"), "分发元数据")
                    }
                });
                ui.renderJson("admin-distribution-output", payload);
                ui.setStatus("admin-distribution-status", "手动分发已排入队列。", "success");
            } catch (error) {
                ui.setStatus("admin-distribution-status", error.message, "error");
            }
        });
    }

    const loadTaskReceiptsButton = ui.byId("load-task-receipts");
    if (loadTaskReceiptsButton) {
        loadTaskReceiptsButton.addEventListener("click", () => {
            const query = buildQueryString([
                ["follow_up_status", ui.readValue("task-receipts-follow-up-status")],
                ["delivery_status", ui.readValue("task-receipts-delivery-status")],
                ["ack_required", readOptionalBooleanSelect("task-receipts-ack-required")],
                ["overdue_only", ui.readCheckbox("task-receipts-overdue-only") ? true : ""],
                ["user_id", readOptionalPositiveInteger("task-receipts-user-id", "回执用户 ID")],
                ["notification_id", ui.readValue("task-receipts-notification-id")],
                ["limit", ui.readNumber("task-receipts-limit", 25)]
            ]);
            loadAdminJson(`/v1/admin/tasks/receipts${query ? `?${query}` : ""}`, "admin-task-receipts-output", "admin-task-receipts-status");
        });
    }

    const escalateTaskReceiptsButton = ui.byId("escalate-task-receipts");
    if (escalateTaskReceiptsButton) {
        escalateTaskReceiptsButton.addEventListener("click", async () => {
            ui.setStatus("admin-task-receipts-status", "正在升级超时回执...");
            try {
                const query = buildQueryString([["limit", ui.readNumber("task-receipts-limit", 25)]]);
                const payload = await requestAdmin("POST", `/v1/admin/tasks/receipts/escalate-overdue?${query}`);
                ui.renderJson("admin-task-receipts-output", payload);
                ui.setStatus("admin-task-receipts-status", "超时回执已处理。", "success");
            } catch (error) {
                ui.setStatus("admin-task-receipts-status", error.message, "error");
            }
        });
    }

    const ackTaskReceiptButton = ui.byId("ack-task-receipt");
    if (ackTaskReceiptButton) {
        ackTaskReceiptButton.addEventListener("click", async () => {
            ui.setStatus("admin-task-receipts-status", "正在确认回执...");
            try {
                const receiptId = ui.readValue("task-receipt-id");
                const payload = await requestAdmin("POST", "/v1/admin/tasks/receipts/ack", {
                    body: { receipt_id: receiptId }
                });
                ui.renderJson("admin-task-receipts-output", payload);
                ui.setStatus("admin-task-receipts-status", payload.message || "回执已确认。", "success");
            } catch (error) {
                ui.setStatus("admin-task-receipts-status", error.message, "error");
            }
        });
    }

    const claimTaskReceiptButton = ui.byId("claim-task-receipt");
    if (claimTaskReceiptButton) {
        claimTaskReceiptButton.addEventListener("click", async () => {
            ui.setStatus("admin-task-receipts-status", "正在领取回执跟进...");
            try {
                const receiptId = ui.readValue("task-receipt-id");
                const payload = await requestAdmin("POST", `/v1/admin/tasks/receipts/${encodeURIComponent(receiptId)}/claim`);
                ui.renderJson("admin-task-receipts-output", payload);
                ui.setStatus("admin-task-receipts-status", payload.message || "回执跟进已领取。", "success");
            } catch (error) {
                ui.setStatus("admin-task-receipts-status", error.message, "error");
            }
        });
    }

    const resolveTaskReceiptButton = ui.byId("resolve-task-receipt");
    if (resolveTaskReceiptButton) {
        resolveTaskReceiptButton.addEventListener("click", async () => {
            ui.setStatus("admin-task-receipts-status", "正在解决回执跟进...");
            try {
                const receiptId = ui.readValue("task-receipt-id");
                const payload = await requestAdmin("POST", `/v1/admin/tasks/receipts/${encodeURIComponent(receiptId)}/resolve`);
                ui.renderJson("admin-task-receipts-output", payload);
                ui.setStatus("admin-task-receipts-status", payload.message || "回执跟进已解决。", "success");
            } catch (error) {
                ui.setStatus("admin-task-receipts-status", error.message, "error");
            }
        });
    }

    const loadTaskOutboxButton = ui.byId("load-task-outbox");
    if (loadTaskOutboxButton) {
        loadTaskOutboxButton.addEventListener("click", () => {
            const query = buildQueryString([
                ["channel", ui.readValue("task-outbox-channel")],
                ["status", ui.readValue("task-outbox-status")],
                ["user_id", readOptionalPositiveInteger("task-outbox-user-id", "发件箱用户 ID")],
                ["notification_id", ui.readValue("task-outbox-notification-id")],
                ["limit", ui.readNumber("task-outbox-limit", 25)]
            ]);
            loadAdminJson(`/v1/admin/tasks/outbox${query ? `?${query}` : ""}`, "admin-task-outbox-output", "admin-task-outbox-status");
        });
    }

    const releaseTaskOutboxButton = ui.byId("release-task-outbox");
    if (releaseTaskOutboxButton) {
        releaseTaskOutboxButton.addEventListener("click", async () => {
            ui.setStatus("admin-task-outbox-status", "正在释放陈旧发件箱任务...");
            try {
                const query = buildQueryString([
                    ["channel", ui.readValue("task-outbox-channel")],
                    ["older_than_minutes", ui.readNumber("task-outbox-older-minutes", 15)],
                    ["limit", ui.readNumber("task-outbox-limit", 25)]
                ]);
                const payload = await requestAdmin("POST", `/v1/admin/tasks/outbox/release-stale?${query}`);
                ui.renderJson("admin-task-outbox-output", payload);
                ui.setStatus("admin-task-outbox-status", payload.message || "已释放陈旧发件箱消息。", "success");
            } catch (error) {
                ui.setStatus("admin-task-outbox-status", error.message, "error");
            }
        });
    }

    const requeueTaskOutboxButton = ui.byId("requeue-task-outbox");
    if (requeueTaskOutboxButton) {
        requeueTaskOutboxButton.addEventListener("click", async () => {
            ui.setStatus("admin-task-outbox-status", "正在重新入队发件箱消息...");
            try {
                const outboxId = ui.readValue("task-outbox-id");
                const payload = await requestAdmin("POST", `/v1/admin/tasks/outbox/${encodeURIComponent(outboxId)}/requeue`);
                ui.renderJson("admin-task-outbox-output", payload);
                ui.setStatus("admin-task-outbox-status", payload.message || "发件箱消息已重新入队。", "success");
            } catch (error) {
                ui.setStatus("admin-task-outbox-status", error.message, "error");
            }
        });
    }

    const retryTaskOutboxButton = ui.byId("retry-task-outbox");
    if (retryTaskOutboxButton) {
        retryTaskOutboxButton.addEventListener("click", async () => {
            ui.setStatus("admin-task-outbox-status", "正在重新入队所选发件箱消息...");
            try {
                const outboxIds = parseCommaSeparated(ui.readValue("task-outbox-ids"));
                if (outboxIds.length === 0) {
                    throw new Error("至少提供一个发件箱 ID。");
                }
                const payload = await requestAdmin("POST", "/v1/admin/tasks/outbox/retry", {
                    body: { outbox_ids: outboxIds }
                });
                ui.renderJson("admin-task-outbox-output", payload);
                ui.setStatus("admin-task-outbox-status", payload.message || "发件箱消息已重新入队。", "success");
            } catch (error) {
                ui.setStatus("admin-task-outbox-status", error.message, "error");
            }
        });
    }

    const loadTaskTradesButton = ui.byId("load-task-trades");
    if (loadTaskTradesButton) {
        loadTaskTradesButton.addEventListener("click", () => {
            const query = buildQueryString([
                ["status", ui.readValue("task-trades-status")],
                ["action", ui.readValue("task-trades-action")],
                ["expired_only", ui.readCheckbox("task-trades-expired-only") ? true : ""],
                ["claimed_only", ui.readCheckbox("task-trades-claimed-only") ? true : ""],
                ["claimed_by_operator_id", readOptionalPositiveInteger("task-trades-claimed-by", "领取操作员 ID")],
                ["user_id", readOptionalPositiveInteger("task-trades-user-id", "交易用户 ID")],
                ["symbol", ui.readValue("task-trades-symbol")],
                ["limit", ui.readNumber("task-trades-limit", 25)]
            ]);
            loadAdminJson(`/v1/admin/tasks/trades${query ? `?${query}` : ""}`, "admin-task-trades-output", "admin-task-trades-status");
        });
    }

    const claimTaskTradesButton = ui.byId("claim-task-trades");
    if (claimTaskTradesButton) {
        claimTaskTradesButton.addEventListener("click", async () => {
            ui.setStatus("admin-task-trades-status", "正在领取交易任务...");
            try {
                const body = {
                    trade_ids: parseCommaSeparated(ui.readValue("task-trades-ids")) || null,
                    limit: ui.readNumber("task-trades-limit", 25),
                    user_id: readOptionalPositiveInteger("task-trades-user-id", "交易用户 ID"),
                    symbol: ui.readValue("task-trades-symbol") || null
                };
                if (!body.trade_ids || body.trade_ids.length === 0) {
                    body.trade_ids = null;
                }
                const payload = await requestAdmin("POST", "/v1/admin/tasks/trades/claim", {
                    operatorRequired: true,
                    body
                });
                ui.renderJson("admin-task-trades-output", payload);
                ui.setStatus("admin-task-trades-status", payload.message || "交易任务已领取。", "success");
            } catch (error) {
                ui.setStatus("admin-task-trades-status", error.message, "error");
            }
        });
    }

    const expireTaskTradesButton = ui.byId("expire-task-trades");
    if (expireTaskTradesButton) {
        expireTaskTradesButton.addEventListener("click", async () => {
            ui.setStatus("admin-task-trades-status", "正在将交易任务设为过期...");
            try {
                const body = {
                    trade_ids: parseCommaSeparated(ui.readValue("task-trades-ids")) || null,
                    limit: ui.readNumber("task-trades-limit", 25),
                    user_id: readOptionalPositiveInteger("task-trades-user-id", "交易用户 ID"),
                    symbol: ui.readValue("task-trades-symbol") || null
                };
                if (!body.trade_ids || body.trade_ids.length === 0) {
                    body.trade_ids = null;
                }
                const payload = await requestAdmin("POST", "/v1/admin/tasks/trades/expire", {
                    body
                });
                ui.renderJson("admin-task-trades-output", payload);
                ui.setStatus("admin-task-trades-status", payload.message || "交易任务已设为过期。", "success");
            } catch (error) {
                ui.setStatus("admin-task-trades-status", error.message, "error");
            }
        });
    }

    const loadUsersButton = ui.byId("load-admin-users");
    if (loadUsersButton) {
        loadUsersButton.addEventListener("click", () => {
            const query = buildQueryString([
                ["query", ui.readValue("admin-users-query")],
                ["plan", ui.readValue("admin-users-plan")],
                ["is_active", readOptionalBooleanSelect("admin-users-active")],
                ["limit", ui.readNumber("admin-users-limit", 25)]
            ]);
            loadAdminJson(`/v1/admin/users${query ? `?${query}` : ""}`, "admin-users-output", "admin-users-status");
        });
    }

    const loadUserDetailButton = ui.byId("load-admin-user-detail");
    if (loadUserDetailButton) {
        loadUserDetailButton.addEventListener("click", () => {
            const userId = readOptionalPositiveInteger("admin-user-id", "用户 ID");
            loadAdminJson(`/v1/admin/users/${userId}`, "admin-users-output", "admin-users-status");
        });
    }

    const updateAdminUserForm = ui.byId("update-admin-user-form");
    if (updateAdminUserForm) {
        updateAdminUserForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("admin-users-status", "正在更新用户...");
            try {
                const userId = readOptionalPositiveInteger("admin-user-id", "用户 ID");
                const body = {};
                const name = ui.readValue("admin-user-name");
                const plan = ui.readValue("admin-user-plan");
                const locale = ui.readValue("admin-user-locale");
                const timezone = ui.readValue("admin-user-timezone");
                const currency = ui.readValue("admin-user-currency");
                const active = readOptionalBooleanSelect("admin-user-is-active");
                const totalCapitalRaw = ui.readValue("admin-user-total-capital");
                const extra = parseOptionalJson(ui.readValue("admin-user-extra"), "用户附加信息");
                if (name) body.name = name;
                if (plan) body.plan = plan;
                if (locale) body.locale = locale;
                if (timezone) body.timezone = timezone;
                if (currency) body.currency = currency;
                if (active !== null) body.is_active = active;
                if (totalCapitalRaw) {
                    const totalCapital = Number(totalCapitalRaw);
                    if (!Number.isFinite(totalCapital) || totalCapital <= 0) {
                        throw new Error("总资金必须是正数。");
                    }
                    body.total_capital = totalCapital;
                }
                if (extra !== null) body.extra = extra;
                if (Object.keys(body).length === 0) {
                    throw new Error("提交前至少填写一项用户变更。");
                }
                const payload = await requestAdmin("PUT", `/v1/admin/users/${userId}`, { body });
                ui.renderJson("admin-users-output", payload);
                ui.setStatus("admin-users-status", "用户已更新。", "success");
            } catch (error) {
                ui.setStatus("admin-users-status", error.message, "error");
            }
        });
    }

    const bulkUpdateUsersForm = ui.byId("bulk-update-users-form");
    if (bulkUpdateUsersForm) {
        bulkUpdateUsersForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("admin-users-status", "正在批量更新用户...");
            try {
                const userIds = parsePositiveIntegers(ui.readValue("admin-bulk-user-ids"));
                if (userIds.length === 0) {
                    throw new Error("批量更新至少需要一个用户 ID。");
                }
                const plan = ui.readValue("admin-bulk-user-plan");
                const isActive = readOptionalBooleanSelect("admin-bulk-user-active");
                if (!plan && isActive === null) {
                    throw new Error("批量更新至少需要套餐或启用状态变更。");
                }
                const body = { user_ids: userIds };
                if (plan) body.plan = plan;
                if (isActive !== null) body.is_active = isActive;
                const payload = await requestAdmin("POST", "/v1/admin/users/bulk", { body });
                ui.renderJson("admin-users-output", payload);
                ui.setStatus("admin-users-status", payload.message || "用户已更新。", "success");
            } catch (error) {
                ui.setStatus("admin-users-status", error.message, "error");
            }
        });
    }

    const loadAuditEventsButton = ui.byId("load-admin-audit");
    if (loadAuditEventsButton) {
        loadAuditEventsButton.addEventListener("click", () => {
            const query = buildQueryString([
                ["entity", ui.readValue("admin-audit-entity")],
                ["entity_id", ui.readValue("admin-audit-entity-id")],
                ["action", ui.readValue("admin-audit-action")],
                ["source", ui.readValue("admin-audit-source")],
                ["status", ui.readValue("admin-audit-status")],
                ["request_id", ui.readValue("admin-audit-request-id")],
                ["limit", ui.readNumber("admin-audit-limit", 25)]
            ]);
            loadAdminJson(`/v1/admin/audit${query ? `?${query}` : ""}`, "admin-audit-output", "admin-audit-status");
        });
    }

    const loadScannerObservabilityButton = ui.byId("load-scanner-observability");
    if (loadScannerObservabilityButton) {
        loadScannerObservabilityButton.addEventListener("click", () => {
            const query = buildQueryString([
                ["status", ui.readValue("admin-scanner-status")],
                ["bucket_id", readOptionalPositiveInteger("admin-scanner-bucket-id", "扫描器分桶 ID")],
                ["symbol", ui.readValue("admin-scanner-symbol")],
                ["decision", ui.readValue("admin-scanner-decision")],
                ["limit", ui.readNumber("admin-scanner-limit", 25)],
                ["decision_limit", ui.readNumber("admin-scanner-decision-limit", 25)]
            ]);
            loadAdminJson(`/v1/admin/scanner/observability${query ? `?${query}` : ""}`, "admin-scanner-output", "admin-scanner-status-output");
        });
    }

    const loadScannerRunButton = ui.byId("load-scanner-run");
    if (loadScannerRunButton) {
        loadScannerRunButton.addEventListener("click", () => {
            const runId = readOptionalPositiveInteger("admin-scanner-run-id", "扫描器运行 ID");
            const query = buildQueryString([
                ["decision_limit", ui.readNumber("admin-scanner-run-decision-limit", 100)]
            ]);
            loadAdminJson(`/v1/admin/scanner/runs/${runId}${query ? `?${query}` : ""}`, "admin-scanner-output", "admin-scanner-status-output");
        });
    }

    const loadScannerLiveDecisionsButton = ui.byId("load-scanner-live-decisions");
    if (loadScannerLiveDecisionsButton) {
        loadScannerLiveDecisionsButton.addEventListener("click", () => {
            const query = buildQueryString([
                ["symbol", ui.readValue("admin-scanner-live-symbol")],
                ["decision", ui.readValue("admin-scanner-live-decision")],
                ["suppressed", readOptionalBooleanSelect("admin-scanner-live-suppressed")],
                ["limit", ui.readNumber("admin-scanner-live-limit", 25)]
            ]);
            loadAdminJson(`/v1/admin/scanner/live-decision${query ? `?${query}` : ""}`, "admin-scanner-output", "admin-scanner-status-output");
        });
    }

    const loadBacktestRunsButton = ui.byId("load-backtest-runs");
    if (loadBacktestRunsButton) {
        loadBacktestRunsButton.addEventListener("click", () => {
            const query = buildQueryString([
                ["status", ui.readValue("admin-backtests-status")],
                ["strategy_name", ui.readValue("admin-backtests-strategy")],
                ["timeframe", ui.readValue("admin-backtests-timeframe")],
                ["symbol", ui.readValue("admin-backtests-symbol")],
                ["limit", ui.readNumber("admin-backtests-limit", 25)]
            ]);
            loadAdminJson(`/v1/admin/backtests/runs${query ? `?${query}` : ""}`, "admin-backtests-output", "admin-backtests-status-output");
        });
    }

    const loadBacktestRunButton = ui.byId("load-backtest-run");
    if (loadBacktestRunButton) {
        loadBacktestRunButton.addEventListener("click", () => {
            const runId = readOptionalPositiveInteger("admin-backtest-run-id", "回测运行 ID");
            loadAdminJson(`/v1/admin/backtests/runs/${runId}`, "admin-backtests-output", "admin-backtests-status-output");
        });
    }

    const loadBacktestRankingsButton = ui.byId("load-backtest-rankings");
    if (loadBacktestRankingsButton) {
        loadBacktestRankingsButton.addEventListener("click", () => {
            const query = buildQueryString([
                ["timeframe", ui.readValue("admin-backtests-rankings-timeframe")],
                ["limit", ui.readNumber("admin-backtests-rankings-limit", 20)]
            ]);
            loadAdminJson(`/v1/admin/backtests/rankings/latest${query ? `?${query}` : ""}`, "admin-backtests-output", "admin-backtests-status-output");
        });
    }

    const triggerBacktestRefreshForm = ui.byId("trigger-backtest-refresh-form");
    if (triggerBacktestRefreshForm) {
        triggerBacktestRefreshForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("admin-backtests-status-output", "正在触发回测刷新...");
            try {
                const symbols = parseCommaSeparated(ui.readValue("admin-backtests-refresh-symbols"));
                const strategyNames = parseCommaSeparated(ui.readValue("admin-backtests-refresh-strategies"));
                const windows = parsePositiveIntegers(ui.readValue("admin-backtests-refresh-windows"));
                const payload = await requestAdmin("POST", "/v1/admin/backtests/runs", {
                    body: {
                        symbols: symbols.length > 0 ? symbols : null,
                        strategy_names: strategyNames.length > 0 ? strategyNames : null,
                        windows: windows.length > 0 ? windows : null,
                        timeframe: ui.readValue("admin-backtests-refresh-timeframe") || "1d"
                    }
                });
                ui.renderJson("admin-backtests-output", payload);
                ui.setStatus("admin-backtests-status-output", "已触发回测刷新。", "success");
            } catch (error) {
                ui.setStatus("admin-backtests-status-output", error.message, "error");
            }
        });
    }

    const overviewButton = ui.byId("load-overview");
    if (overviewButton) {
        overviewButton.addEventListener("click", () => {
            loadAdminJson(`/v1/admin/analytics/overview?window_hours=${readWindowHours()}`, "admin-analytics-output", "admin-analytics-status");
        });
    }

    const distributionButton = ui.byId("load-distribution");
    if (distributionButton) {
        distributionButton.addEventListener("click", () => {
            loadAdminJson(`/v1/admin/analytics/distribution?window_hours=${readWindowHours()}`, "admin-analytics-output", "admin-analytics-status");
        });
    }

    const strategyButton = ui.byId("load-strategy-health");
    if (strategyButton) {
        strategyButton.addEventListener("click", () => {
            loadAdminJson(`/v1/admin/analytics/strategy-health?window_hours=${readWindowHours()}`, "admin-analytics-output", "admin-analytics-status");
        });
    }

    const tradingagentsButton = ui.byId("load-tradingagents");
    if (tradingagentsButton) {
        tradingagentsButton.addEventListener("click", () => {
            loadAdminJson(`/v1/admin/analytics/tradingagents?window_hours=${readWindowHours()}`, "admin-analytics-output", "admin-analytics-status");
        });
    }

    const runtimeHealthButton = ui.byId("load-runtime-health");
    if (runtimeHealthButton) {
        runtimeHealthButton.addEventListener("click", () => {
            loadAdminJson("/v1/admin/runtime/health", "admin-runtime-output", "admin-runtime-status");
        });
    }

    const runtimeMetricsButton = ui.byId("load-runtime-metrics");
    if (runtimeMetricsButton) {
        runtimeMetricsButton.addEventListener("click", () => {
            loadAdminJson("/v1/admin/runtime/metrics", "admin-runtime-output", "admin-runtime-status");
        });
    }

    const runtimeAlertsButton = ui.byId("load-runtime-alerts");
    if (runtimeAlertsButton) {
        runtimeAlertsButton.addEventListener("click", () => {
            loadAdminJson("/v1/admin/runtime/alerts", "admin-runtime-output", "admin-runtime-status");
        });
    }

    const acceptanceStatusButton = ui.byId("load-acceptance-status");
    if (acceptanceStatusButton) {
        acceptanceStatusButton.addEventListener("click", () => {
            loadAdminJson("/v1/admin/acceptance/status", "admin-acceptance-output", "admin-acceptance-status");
        });
    }

    const acceptanceReportButton = ui.byId("load-acceptance-report");
    if (acceptanceReportButton) {
        acceptanceReportButton.addEventListener("click", () => {
            loadAdminJson("/v1/admin/acceptance/report", "admin-acceptance-output", "admin-acceptance-status");
        });
    }

    ui.renderSessionSnapshot("admin-session-output");
});
"""

_BASE_CONNECTION_PANEL = """
<section class=\"panel span-4 surface-connection\" id=\"surface-connection\">
    <div class=\"panel-header\">
        <div>
            <h2>环境与接口地址</h2>
            <p class=\"panel-copy\">并行版页面由 Python 直接渲染。若你绕过 nginx、直接命中 public-api，请先在这里校准 public / admin 两套接口基址。</p>
        </div>
        <span class=\"pill\">环境配置</span>
    </div>
    <p class=\"panel-note\">保存后会写入当前浏览器本地存储，便于在不同端口或反向代理入口之间快速切换。</p>
    <div class=\"field-grid\">
        <label>
            Public API 基础地址
            <input id=\"public-api-base\" type=\"url\" placeholder=\"http://localhost:8000\">
        </label>
        <label>
            Admin API 基础地址
            <input id=\"admin-api-base\" type=\"url\" placeholder=\"http://localhost:8080\">
        </label>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" class=\"secondary\" id=\"save-base-urls\">保存接口地址</button>
    </div>
    <div class=\"status\" id=\"base-url-status\"></div>
</section>
"""

_APP_BODY = """
<section class=\"panel wide app-overview\" id=\"app-overview\">
    <div class=\"panel-header\">
        <div>
            <h2>移动订阅流程</h2>
            <p class=\"panel-copy\">next/app 现在更像正式移动投资产品：流程短、动作少、优先单用户资产录入，最后再一次性启动订阅。</p>
        </div>
        <span class=\"pill\">正式移动产品</span>
    </div>
    <div class=\"journey-strip\">
        <article class=\"journey-step\">
            <small>Step 01</small>
            <strong>登录设备</strong>
            <span>邮箱验证码完成登录，保存会话后可继续回到本地草稿，不会打断录入。</span>
        </article>
        <article class=\"journey-step\">
            <small>Step 02</small>
            <strong>整理资产草稿</strong>
            <span>先录入订阅股票、已持仓和现金，再由系统校验同步前置条件。</span>
        </article>
        <article class=\"journey-step\">
            <small>Step 03</small>
            <strong>启动订阅</strong>
            <span>确认无误后，把这次监控快照一次性同步到服务端，供桌面端和策略端消费。</span>
        </article>
    </div>
    <div class=\"section-nav\">
        <a class=\"section-link\" href=\"#app-account\">账户与设备</a>
        <a class=\"section-link\" href=\"#app-draft\">资产草稿</a>
        <a class=\"section-link\" href=\"#app-watchlist\">订阅股票</a>
        <a class="section-link" href="#platform-console">策略实验</a>
        <a class=\"section-link\" href=\"#app-launch\">开始订阅</a>
    </div>
</section>

<section class=\"panel wide\" id=\"app-account\">
    <div class=\"panel-header\">
        <div>
            <h2>账户与当前设备</h2>
            <p class=\"panel-copy\">把登录动作收敛成移动端常见的两步：先发送验证码，再验证并保留会话。登录成功后，这个设备上的本地草稿和云端状态会在同一视图里汇总。</p>
        </div>
        <span class=\"pill\">账户接入</span>
    </div>
    <div class=\"split-shell\">
        <div class=\"stack-flow\">
            <div class=\"subpanel\">
                <h3>发送验证码</h3>
                <p>普通用户只需邮箱验证码即可登录，不要求复杂密码流。</p>
                <form id=\"send-code-form\">
                    <div class=\"field-grid single\">
                        <label>
                            邮箱
                            <input id=\"auth-email\" type=\"email\" placeholder=\"user@example.com\" required>
                        </label>
                    </div>
                            <input id="platform-endpoint-filter" type="text" placeholder="例如：scanner, backtests, trades">
                        <button type=\"submit\">发送验证码</button>
                    </div>
                </form>
            </div>
            <div class=\"subpanel\">
                <h3>验证并保存会话</h3>
                <p>验证通过后写入本地会话，后续恢复云端草稿或开始订阅都复用这份会话。</p>
                <form id=\"verify-form\">
                    <div class=\"field-grid\">
                        <label>
                            验证邮箱
                            <input id=\"verify-email\" type=\"email\" placeholder=\"user@example.com\" required>
                        </label>
                        <label>
                            6 位验证码
                            <input id=\"verify-code\" type=\"text\" maxlength=\"6\" placeholder=\"123456\" required>
                        </label>
                        <label>
                            语言地区
                            <input id=\"verify-locale\" type=\"text\" placeholder=\"zh-CN\">
                        </label>
                        <label>
                            时区
                            <input id=\"verify-timezone\" type=\"text\" placeholder=\"Asia/Shanghai\">
                        </label>
                    </div>
                    <div class=\"button-row\">
                        <button type=\"submit\">验证并保存会话</button>
                        <button type=\"button\" class=\"secondary\" id=\"refresh-session\">刷新令牌</button>
                        <button type=\"button\" class=\"ghost\" id=\"logout-session\">退出登录</button>
                    </div>
                </form>
                <div class=\"button-row\">
                    <button type=\"button\" class=\"secondary\" id=\"restore-remote-draft\">从云端恢复资料</button>
                </div>
                <div class=\"status\" id=\"auth-status\"></div>
            </div>
        </div>
        <aside class=\"phone-shell\">
            <h3>设备侧会话卡片</h3>
            <p>把当前账号、订阅状态和最近一次同步结果放进更像移动 app 的设备视图里，方便在窄屏下快速确认。</p>
            <div class=\"phone-chip-row\">
                <span class=\"phone-chip\">邮箱验证码登录</span>
                <span class=\"phone-chip\">本地草稿常驻</span>
                <span class=\"phone-chip\">支持云端恢复</span>
            </div>
            <div class=\"table-wrap\" id=\"subscriber-session-panel\"><div class=\"empty-state\">登录后，这里会显示当前账号、方案和最近一次订阅状态。</div></div>
        </aside>
    </div>
</section>

<section class=\"panel wide\" id=\"app-draft\">
    <div class=\"panel-header\">
        <div>
            <h2>资产草稿总览</h2>
            <p class=\"panel-copy\">这部分像移动投资产品里的资产准备页：先看总览，再决定是否继续修改 watchlist、持仓或现金。</p>
        </div>
    </div>
    <div class=\"split-shell\">
        <div>
            <div class=\"hero-grid\">
                <div class=\"hero-stat\">
                    <strong id=\"draft-watchlist-count\">0</strong>
                    <span>订阅股票</span>
                </div>
                <div class=\"hero-stat\">
                    <strong id=\"draft-portfolio-count\">0</strong>
                    <span>已持仓股票</span>
                </div>
                <div class=\"hero-stat\">
                    <strong id=\"draft-cash-amount\">0</strong>
                    <span>现金</span>
                </div>
                <div class=\"hero-stat\">
                    <strong id=\"draft-total-assets\">0</strong>
                    <span>估算总资产</span>
                </div>
            </div>
            <p class=\"token-note\" id=\"draft-sync-note\">浏览器会自动保留草稿；只有“开始订阅”时才会把监控快照同步到服务端。</p>
            <div class=\"button-row\">
                <button type=\"button\" class=\"secondary\" id=\"save-local-draft\">手动保存草稿</button>
                <button type=\"button\" class=\"ghost\" id=\"clear-local-draft\">清空本地草稿</button>
            </div>
            <div class=\"status\" id=\"draft-status\"></div>
        </div>
        <div class=\"subpanel\">
            <h3>同步前检查</h3>
            <p>把同步门槛明确告诉用户，避免在最后一步才发现缺少持仓或现金。</p>
            <ul class=\"micro-list\">
                <li>先确定订阅股票数量与最低分数，避免一开始监控范围过宽。</li>
                <li>如果当前持有仓位，请在这里录入数量、成本和止盈止损阈值。</li>
                <li>同步前确认现金与币种，便于桌面端估算总资产与风控空间。</li>
            </ul>
            <div class=\"table-wrap\" id=\"draft-summary-panel\"><div class=\"empty-state\">登录后录入订阅股票、持仓和现金，这里会显示同步准备状态。</div></div>
        </div>
    </div>
</section>

<section class=\"panel wide\" id=\"app-watchlist\">
    <div class=\"panel-header\">
        <div>
            <h2>订阅股票</h2>
            <p class=\"panel-copy\">把关注标的组织成正式产品里的 watchlist 编辑器。输入支持批量粘贴，右侧持续展示当前草稿。</p>
        </div>
        <span class=\"pill\">本地草稿</span>
    </div>
    <div class=\"split-shell\">
        <div class=\"subpanel\">
            <h3>添加监控标的</h3>
            <p>支持逗号、空格或换行批量录入；移动端优先减少切换页面次数。</p>
            <form id=\"draft-watchlist-form\">
                <div class=\"field-grid\">
                    <label>
                        股票代码
                        <textarea id=\"draft-watchlist-symbols\" placeholder=\"AAPL, TSLA, NVDA\" required></textarea>
                    </label>
                    <label>
                        默认过滤分数
                        <input id=\"draft-watchlist-score\" type=\"number\" min=\"0\" max=\"100\" value=\"65\">
                    </label>
                </div>
                <label class=\"inline-check\">
                    <input id=\"draft-watchlist-notify\" type=\"checkbox\" checked>
                    新信号触发时通知我
                </label>
                <div class=\"button-row\">
                    <button type=\"submit\">加入订阅草稿</button>
                </div>
            </form>
            <div class=\"status\" id=\"watchlist-draft-status\"></div>
        </div>
        <div class=\"subpanel\">
            <h3>当前订阅列表</h3>
            <p>这里持续显示当前已准备同步的标的清单，方便在移动端单页完成确认。</p>
            <div class=\"table-wrap\" id=\"draft-watchlist-table\"><div class=\"empty-state\">还没有订阅股票。加入后，桌面端会把它们作为监控候选列表。</div></div>
        </div>
    </div>
</section>

<section class=\"panel wide\" id=\"app-portfolio\">
    <div class=\"panel-header\">
        <div>
            <h2>已持仓股票</h2>
            <p class=\"panel-copy\">像成熟券商 app 一样把当前持仓放在独立步骤里，强调仓位成本、盈亏阈值与备注，不把风控字段藏在次级页面。</p>
        </div>
        <span class=\"pill\">本地草稿</span>
    </div>
    <div class=\"split-shell\">
        <div class=\"subpanel\">
            <h3>录入持仓与阈值</h3>
            <p>把买入成本、止盈止损和备注作为一等输入项，减少用户启动订阅后的二次修改。</p>
            <form id=\"draft-portfolio-form\">
                <div class=\"field-grid\">
                    <label>
                        股票代码
                        <input id=\"draft-portfolio-symbol\" type=\"text\" placeholder=\"AAPL\" required>
                    </label>
                    <label>
                        持股数量
                        <input id=\"draft-portfolio-shares\" type=\"number\" min=\"1\" step=\"1\" value=\"10\" required>
                    </label>
                    <label>
                        持仓均价
                        <input id=\"draft-portfolio-cost\" type=\"number\" min=\"0.01\" step=\"0.01\" value=\"150\" required>
                    </label>
                    <label>
                        止盈目标
                        <input id=\"draft-portfolio-target\" type=\"number\" min=\"0.01\" max=\"1\" step=\"0.01\" value=\"0.15\">
                    </label>
                    <label>
                        止损阈值
                        <input id=\"draft-portfolio-stop\" type=\"number\" min=\"0.01\" max=\"1\" step=\"0.01\" value=\"0.08\">
                    </label>
                    <label>
                        备注
                        <input id=\"draft-portfolio-notes\" type=\"text\" placeholder=\"例如：长期持有 / 波段仓位\">
                    </label>
                </div>
                <label class=\"inline-check\">
                    <input id=\"draft-portfolio-notify\" type=\"checkbox\" checked>
                    持仓相关信号也通知我
                </label>
                <div class=\"button-row\">
                    <button type=\"submit\">加入或覆盖持仓</button>
                    <button type=\"button\" class=\"ghost\" id=\"reset-portfolio-form\">清空表单</button>
                </div>
            </form>
            <div class=\"status\" id=\"portfolio-draft-status\"></div>
        </div>
        <div class=\"subpanel\">
            <h3>持仓草稿列表</h3>
            <p>空仓场景也在同一页面处理，避免把“允许空仓启动”隐藏到设置里。</p>
            <div class=\"table-wrap\" id=\"draft-portfolio-table\"><div class=\"empty-state\">还没有已持仓股票。如果当前空仓，请在开始订阅前勾选“允许空仓启动”。</div></div>
        </div>
    </div>
</section>

<section class=\"panel wide\" id=\"app-launch\">
    <div class=\"panel-header\">
        <div>
            <h2>现金与开始订阅</h2>
            <p class=\"panel-copy\">把最终启动动作收口成单一主按钮。先确认现金和币种，再决定是否允许空仓启动，最后一次性写入服务端监控快照。</p>
        </div>
        <span class=\"pill\">POST /v1/account/start-subscription</span>
    </div>
    <div class=\"split-shell\">
        <div class=\"stack-flow\">
            <div class=\"subpanel\">
                <h3>最终确认</h3>
                <p>同步前只保留最关键的资产输入和一个主动作按钮，符合移动端的主路径原则。</p>
                <div class=\"field-grid\">
                    <label>
                        可用现金
                        <input id=\"draft-cash-input\" type=\"number\" min=\"0\" step=\"0.01\" placeholder=\"50000\" required>
                    </label>
                    <label>
                        币种
                        <input id=\"draft-currency-input\" type=\"text\" placeholder=\"USD\" value=\"USD\">
                    </label>
                </div>
                <label class=\"inline-check\">
                    <input id=\"draft-allow-empty-portfolio\" type=\"checkbox\">
                    我当前是空仓，只同步订阅股票和现金
                </label>
                <div class=\"button-row\">
                    <button type=\"button\" id=\"start-subscription-button\">开始订阅</button>
                </div>
                <div class=\"status\" id=\"subscription-sync-status\"></div>
            </div>
            <div class=\"subpanel\">
                <h3>同步后的产品反馈</h3>
                <p>启动成功后，桌面监控端会把这次同步当作最新有效快照，后续研究与信号都从这里展开。</p>
                <ul class=\"micro-list\">
                    <li>订阅股票会进入平台端与扫描器的关注范围。</li>
                    <li>已持仓与现金会成为总资产估算与风控提醒的基础数据。</li>
                    <li>如果用户后续调整草稿，需要重新执行一次“开始订阅”。</li>
                </ul>
            </div>
        </div>
        <aside class=\"phone-shell\">
            <h3>同步结果预览</h3>
            <p>右侧保留一个更像成品 app 的结果卡片，用来承接启动后的回包、错误或服务端回执。</p>
            <div class=\"phone-chip-row\">
                <span class=\"phone-chip\">单一主操作</span>
                <span class=\"phone-chip\">结果即时反馈</span>
                <span class=\"phone-chip\">可回滚到草稿修改</span>
            </div>
            <div class=\"table-wrap\" id=\"subscription-sync-panel\"><div class=\"empty-state\">填写完订阅股票、持仓和现金后，点击“开始订阅”即可把监控快照同步到桌面端。</div></div>
        </aside>
    </div>
</section>
"""

_PLATFORM_BODY = _BASE_CONNECTION_PANEL + """
<section class=\"panel span-4\" id=\"platform-session\">
    <div class=\"panel-header\">
        <div>
            <h2>共享会话快照</h2>
            <p class=\"panel-copy\">平台工作台默认复用 next/app 已保存的用户 Bearer 会话，方便在策略研究、仓位调整和交易执行之间连续工作。</p>
        </div>
        <span class=\"pill\">令牌复用</span>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" class=\"secondary\" id=\"show-platform-session\">查看当前会话</button>
        <button type=\"button\" class=\"ghost\" id=\"clear-platform-session\">清除公共会话</button>
    </div>
    <div class=\"status\" id=\"platform-session-status\"></div>
    <pre class=\"json-output\" id=\"platform-session-output\"></pre>
</section>

<section class=\"panel span-4 platform-command-panel\" id=\"platform-command\">
    <div class=\"panel-header\">
        <div>
            <h2>策略核心导航</h2>
            <p class=\"panel-copy\">把候选标的、买入预警、退出策略、交易执行与内部策略接口统一收回桌面端，让平台一眼看上去就是策略核心。</p>
        </div>
        <span class=\"pill\">策略核心</span>
    </div>
    <div class=\"command-strip\">
        <article class=\"command-card\">
            <small>Lane 01</small>
            <strong>入场策略</strong>
            <span>围绕候选标的、观察池和买入预警条件建立可执行的入场策略池。</span>
        </article>
        <article class=\"command-card\">
            <small>Lane 02</small>
            <strong>退出策略</strong>
            <span>持仓、止盈止损和退出节奏在同一工作台联动维护，不拆到别的产品面。</span>
        </article>
        <article class=\"command-card\">
            <small>Lane 03</small>
            <strong>策略实验</strong>
            <span>回测、胜率、排名和内部策略接口都应服务平台核心，而不是成为 admin 的主界面。</span>
        </article>
        <article class=\"command-card\">
            <small>Lane 04</small>
            <strong>执行闭环</strong>
            <span>从信号判断到交易确认尽量不离开桌面端，保持策略到执行的连续性。</span>
        </article>
    </div>
    <div class=\"section-nav\">
        <a class=\"section-link\" href=\"#platform-research\">候选标的</a>
        <a class=\"section-link\" href=\"#platform-positions\">策略组合</a>
        <a class=\"section-link\" href=\"#platform-trades\">交易执行</a>
        <a class=\"section-link\" href=\"#platform-console\">策略实验</a>
    </div>
    <ul class=\"micro-list\">
        <li>平台端不是资料页，而是策略核心工作台，入场与退出逻辑都应在这里闭环。</li>
        <li>高权限策略接口即使暂时经由内部 API 提供，产品归属也仍然属于平台端。</li>
        <li>交易执行与结果确认要紧贴策略判断，而不是散落到别的后台面板。</li>
    </ul>
</section>

<section class=\"panel span-8\" id=\"platform-research\">
    <div class=\"panel-header\">
        <div>
            <h2>候选标的与入场研究</h2>
            <p class=\"panel-copy\">这里是买入预警策略的候选池入口。搜索结果、原始回包和后续观察池操作保留在同一屏，方便快速形成入场判断。</p>
        </div>
        <span class=\"pill\">/v1/search/symbols</span>
    </div>
    <div class=\"subpanel\">
        <h3>候选标的池</h3>
        <p>搜索结果点击后可直接回填到下方策略观察池，减少从研究到入场筛选之间的切换成本。</p>
        <form id=\"symbol-search-form\">
            <div class=\"field-grid\">
                <label>
                    搜索词
                    <input id=\"search-query\" type=\"text\" placeholder=\"AAPL 或 台积电\" required>
                </label>
                <label>
                    资产类型
                    <input id=\"search-type\" type=\"text\" placeholder=\"stock, etf, crypto\">
                </label>
                <label>
                    数量上限
                    <input id=\"search-limit\" type=\"number\" min=\"1\" max=\"50\" value=\"20\">
                </label>
            </div>
            <div class=\"button-row\">
                <button type=\"submit\">搜索标的</button>
            </div>
        </form>
        <div class=\"status\" id=\"search-status\"></div>
    </div>
    <div class=\"split-shell\">
        <div class=\"table-wrap\" id=\"search-results\"><div class=\"empty-state\">搜索结果会显示在这里。</div></div>
        <pre class=\"json-output\" id=\"search-output\"></pre>
    </div>
</section>

<section class=\"panel span-4 tall\" id=\"platform-positions\">
    <div class=\"panel-header\">
        <div>
            <h2>策略组合：观察池与持仓</h2>
            <p class=\"panel-copy\">这里不是普通资料页，而是平台策略状态面：入场观察池、已有持仓和退出参数在同一侧栏里维护。</p>
        </div>
        <span class=\"pill\">用户 API</span>
    </div>
    <div class=\"stack-flow\">
        <div class=\"subpanel\">
            <h3>入场观察池</h3>
            <p>研究结果可以直接回填到这里，把候选标的转成真正的买入预警监控列表。</p>
            <form id=\"platform-watchlist-form\">
                <div class=\"field-grid\">
                    <label>
                        代码
                        <input id=\"platform-watchlist-symbol\" type=\"text\" placeholder=\"AAPL\" required>
                    </label>
                    <label>
                        最低分数
                        <input id=\"platform-watchlist-score\" type=\"number\" min=\"0\" max=\"100\" value=\"70\">
                    </label>
                </div>
                <label class=\"inline-check\">
                    <input id=\"platform-watchlist-notify\" type=\"checkbox\" checked>
                    该标的满足买入条件时通知我
                </label>
                <div class=\"button-row\">
                    <button type=\"submit\">加入观察列表</button>
                    <button type=\"button\" class=\"secondary\" id=\"platform-load-watchlist\">加载观察列表</button>
                    <button type=\"button\" class=\"ghost\" id=\"platform-load-portfolio\">加载持仓</button>
                </div>
            </form>
            <div class=\"status\" id=\"platform-watchlist-status\"></div>
            <pre class=\"json-output\" id=\"platform-watchlist-output\"></pre>
        </div>
        <div class=\"subpanel\">
            <h3>退出策略与持仓</h3>
            <p>这里对应 <code>POST /v1/portfolio</code>，用于把持仓、止盈止损和退出提醒放进同一套退出策略工作流。</p>
            <form id=\"platform-portfolio-form\">
                <div class=\"field-grid\">
                    <label>
                        持仓代码
                        <input id=\"platform-portfolio-symbol\" type=\"text\" placeholder=\"AAPL\" required>
                    </label>
                    <label>
                        股数
                        <input id=\"platform-portfolio-shares\" type=\"number\" min=\"0.0001\" step=\"0.0001\" value=\"10\">
                    </label>
                    <label>
                        平均成本
                        <input id=\"platform-portfolio-avg-cost\" type=\"number\" min=\"0.0001\" step=\"0.0001\" value=\"150\">
                    </label>
                    <label>
                        止盈目标
                        <input id=\"platform-portfolio-target\" type=\"number\" step=\"0.0001\" min=\"0\" max=\"1\" value=\"0.15\">
                    </label>
                    <label>
                        止损阈值
                        <input id=\"platform-portfolio-stop\" type=\"number\" step=\"0.0001\" min=\"0\" max=\"1\" value=\"0.08\">
                    </label>
                </div>
                <label class=\"inline-check\">
                    <input id=\"platform-portfolio-notify\" type=\"checkbox\" checked>
                    该持仓触发退出条件时通知我
                </label>
                <label>
                    持仓备注
                    <input id=\"platform-portfolio-notes\" type=\"text\" placeholder=\"建仓原因、风控备注等\">
                </label>
                <div class=\"button-row\">
                    <button type=\"submit\" class=\"secondary\">新增持仓</button>
                </div>
            </form>
            <div class=\"status\" id=\"platform-portfolio-status\"></div>
            <pre class=\"json-output\" id=\"platform-portfolio-output\"></pre>
        </div>
    </div>
</section>

<section class=\"panel span-7\" id=\"platform-maintenance\">
    <div class=\"panel-header\">
        <div>
            <h2>策略参数维护</h2>
            <p class=\"panel-copy\">观察池和持仓参数的更新动作被视为策略维护的一部分，而不是附属数据编辑页面。</p>
        </div>
        <span class=\"pill\">策略参数编辑</span>
    </div>
    <div class=\"stack-flow\">
        <div class=\"subpanel\">
            <h3>入场参数维护</h3>
            <p>适合在信号筛选前快速调整单个观察项的阈值、提醒和入场筛选条件。</p>
            <form id=\"platform-update-watchlist-form\">
                <div class=\"field-grid\">
                    <label>
                        观察项 ID
                        <input id=\"platform-watchlist-item-id\" type=\"number\" min=\"1\" placeholder=\"1\" required>
                    </label>
                    <label>
                        新最低分数
                        <input id=\"platform-watchlist-update-score\" type=\"number\" min=\"0\" max=\"100\" placeholder=\"80\">
                    </label>
                    <label>
                        通知状态
                        <select id=\"platform-watchlist-update-notify\">
                            <option value=\"\">保持当前</option>
                            <option value=\"true\">启用</option>
                            <option value=\"false\">停用</option>
                        </select>
                    </label>
                </div>
                <div class=\"button-row\">
                    <button type=\"submit\" class=\"secondary\">更新观察项</button>
                    <button type=\"button\" class=\"ghost\" id=\"platform-delete-watchlist-item\">删除观察项</button>
                </div>
            </form>
        </div>
        <div class=\"subpanel\">
            <h3>退出参数维护</h3>
            <p>把股数、成本、止盈止损和退出提醒这些高频维护动作压缩到一屏里完成。</p>
            <form id=\"platform-update-portfolio-form\">
                <div class=\"field-grid\">
                    <label>
                        持仓条目 ID
                        <input id=\"platform-portfolio-item-id\" type=\"number\" min=\"1\" placeholder=\"1\" required>
                    </label>
                    <label>
                        股数
                        <input id=\"platform-portfolio-update-shares\" type=\"number\" min=\"1\" placeholder=\"10\">
                    </label>
                    <label>
                        平均成本
                        <input id=\"platform-portfolio-update-cost\" type=\"number\" step=\"0.01\" min=\"0.01\" placeholder=\"150\">
                    </label>
                    <label>
                        止盈目标
                        <input id=\"platform-portfolio-update-target\" type=\"number\" step=\"0.01\" min=\"0.01\" max=\"1\" placeholder=\"0.2\">
                    </label>
                    <label>
                        止损阈值
                        <input id=\"platform-portfolio-update-stop\" type=\"number\" step=\"0.01\" min=\"0.01\" max=\"1\" placeholder=\"0.08\">
                    </label>
                    <label>
                        通知状态
                        <select id=\"platform-portfolio-update-notify\">
                            <option value=\"\">保持当前</option>
                            <option value=\"true\">启用</option>
                            <option value=\"false\">停用</option>
                        </select>
                    </label>
                </div>
                <label>
                    备注
                    <input id=\"platform-portfolio-update-notes\" type=\"text\" placeholder=\"更新后的持仓理由\">
                </label>
                <div class=\"button-row\">
                    <button type=\"submit\" class=\"secondary\">更新持仓</button>
                    <button type=\"button\" class=\"ghost\" id=\"platform-delete-portfolio-item\">删除持仓</button>
                </div>
            </form>
        </div>
    </div>
    <div class=\"status\" id=\"platform-maintenance-status\"></div>
    <pre class=\"json-output\" id=\"platform-maintenance-output\"></pre>
</section>

<section class=\"panel span-5\" id=\"platform-trades\">
    <div class=\"panel-header\">
        <div>
            <h2>交易执行与回执</h2>
            <p class=\"panel-copy\">策略确认后的执行面仍属于平台核心。这里保留应用内交易和公开交易两条路径，用于形成完整执行闭环。</p>
        </div>
        <span class=\"pill\">/v1/trades/*</span>
    </div>
    <form id=\"app-trade-form\">
        <div class=\"field-grid single\">
            <label>
                已登录 app-info 的交易 ID
                <input id=\"app-trade-id\" type=\"text\" placeholder=\"trade-123\" required>
            </label>
        </div>
        <div class=\"button-row\">
            <button type=\"submit\">加载应用交易信息</button>
            <button type=\"button\" class=\"secondary\" id=\"app-confirm-trade\">确认交易</button>
            <button type=\"button\" class=\"ghost\" id=\"app-ignore-trade\">忽略交易</button>
        </div>
    </form>
    <div class=\"field-grid\">
        <label>
            用于调整的实际股数
            <input id=\"app-adjust-shares\" type=\"number\" min=\"0.0001\" step=\"0.0001\" value=\"10\">
        </label>
        <label>
            用于调整的实际价格
            <input id=\"app-adjust-price\" type=\"number\" min=\"0.0001\" step=\"0.0001\" value=\"150\">
        </label>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" class=\"secondary\" id=\"app-adjust-trade\">调整并确认</button>
    </div>
    <form id=\"public-trade-form\">
        <div class=\"field-grid\">
            <label>
                公开交易 ID
                <input id=\"public-trade-id\" type=\"text\" placeholder=\"trade-123\" required>
            </label>
            <label>
                公开链接 Token
                <input id=\"public-trade-token\" type=\"text\" placeholder=\"token-123\" required>
            </label>
        </div>
        <div class=\"button-row\">
            <button type=\"submit\" class=\"secondary\">加载公开交易信息</button>
        </div>
    </form>
    <div class=\"field-grid\">
        <label>
            公开调整股数
            <input id=\"public-adjust-shares\" type=\"number\" min=\"0.0001\" step=\"0.0001\" value=\"10\">
        </label>
        <label>
            公开调整价格
            <input id=\"public-adjust-price\" type=\"number\" min=\"0.0001\" step=\"0.0001\" value=\"150\">
        </label>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" class=\"secondary\" id=\"public-confirm-trade\">公开确认交易</button>
        <button type=\"button\" class=\"ghost\" id=\"public-ignore-trade\">公开忽略交易</button>
        <button type=\"button\" class=\"secondary\" id=\"public-adjust-trade\">公开调整并确认</button>
    </div>
    <div class=\"status\" id=\"trade-status\"></div>
    <pre class=\"json-output\" id=\"trade-output\"></pre>
</section>

<section class=\"panel span-4\" id=\"platform-matrix\">
    <div class=\"panel-header\">
        <div>
            <h2>策略能力矩阵</h2>
            <p class=\"panel-copy\">这里用来快速盘点平台是否已经覆盖选股、预警、退出、执行和实验所需的接口能力。</p>
        </div>
        <span class=\"pill\">策略覆盖索引</span>
    </div>
    <div class=\"field-grid\">
        <label>
            筛选关键字
            <input id=\"platform-endpoint-filter\" type=\"text\" placeholder=\"例如：scanner, backtests, trades\">
        </label>
        <label>
            当前统计
            <input id=\"platform-endpoint-summary\" type=\"text\" readonly>
        </label>
    </div>
    <div class=\"table-wrap\" id=\"platform-endpoint-matrix\"><div class=\"empty-state\">正在加载端点矩阵...</div></div>
    <div class=\"status\" id=\"platform-endpoint-status\"></div>
</section>

<section class=\"panel span-8\" id=\"platform-console\">
    <div class=\"panel-header\">
        <div>
            <h2>策略实验与观测</h2>
            <p class=\"panel-copy\">把 scanner、backtests、signal stats 与 strategy health 直接拉回桌面端。admin token 在这里只是高权限取数凭证，不再要求你切到另一个产品面做核心策略判断。</p>
        </div>
        <span class=\"pill\">策略实验</span>
    </div>
    <div class=\"stack-flow\">
        <div class=\"split-shell\">
            <div class=\"subpanel\">
                <h3>高权限策略凭证</h3>
                <p>这些接口暂时仍走 admin API，但平台页现在可以直接完成 admin-auth 发码、验证、刷新与手动 token 覆盖，不必先切去 admin 页拿到一份可用 session。</p>
                <form id=\"platform-admin-send-code-form\">
                    <div class=\"field-grid\">
                        <label>
                            管理员邮箱
                            <input id=\"platform-admin-auth-email\" type=\"email\" placeholder=\"admin@example.com\" required>
                        </label>
                        <label>
                            语言地区
                            <input id=\"platform-admin-verify-locale\" type=\"text\" placeholder=\"zh-CN\" value=\"zh-CN\">
                        </label>
                    </div>
                    <div class=\"button-row\">
                        <button type=\"submit\">发送管理验证码</button>
                    </div>
                </form>
                <form id=\"platform-admin-verify-form\">
                    <div class=\"field-grid\">
                        <label>
                            验证邮箱
                            <input id=\"platform-admin-verify-email\" type=\"email\" placeholder=\"admin@example.com\" required>
                        </label>
                        <label>
                            6 位验证码
                            <input id=\"platform-admin-verify-code\" type=\"text\" maxlength=\"6\" placeholder=\"123456\" required>
                        </label>
                        <label>
                            时区
                            <input id=\"platform-admin-verify-timezone\" type=\"text\" placeholder=\"Asia/Shanghai\" value=\"Asia/Shanghai\">
                        </label>
                    </div>
                    <div class=\"button-row\">
                        <button type=\"submit\" class=\"secondary\">验证并保存策略会话</button>
                        <button type=\"button\" class=\"ghost\" id=\"platform-refresh-admin-session\">刷新策略会话</button>
                    </div>
                </form>
                <label>
                    管理 Bearer Token
                    <textarea id=\"platform-admin-token\" placeholder=\"在此粘贴高权限策略 Bearer Token\"></textarea>
                </label>
                <div class=\"button-row\">
                    <button type=\"button\" id=\"platform-save-admin-token\">保存策略令牌</button>
                    <button type=\"button\" class=\"secondary\" id=\"platform-show-admin-session\">查看权限状态</button>
                    <button type=\"button\" class=\"ghost\" id=\"platform-clear-admin-token\">清除策略令牌</button>
                </div>
                <div class=\"status\" id=\"platform-admin-token-status\"></div>
                <pre class=\"json-output\" id=\"platform-admin-session-output\"></pre>
            </div>
            <div class=\"subpanel\">
                <h3>策略快览</h3>
                <p>先看策略健康度、信号摘要和分析总览，再决定是否继续下钻到 scanner 运行或回测实验。</p>
                <div class=\"field-grid\">
                    <label>
                        时间窗口（小时）
                        <input id=\"platform-strategy-window-hours\" type=\"number\" min=\"1\" max=\"720\" value=\"24\">
                    </label>
                    <label>
                        排名周期
                        <input id=\"platform-backtests-rankings-timeframe\" type=\"text\" value=\"1d\" placeholder=\"1d\">
                    </label>
                    <label>
                        排名上限
                        <input id=\"platform-backtests-rankings-limit\" type=\"number\" min=\"1\" max=\"100\" value=\"20\">
                    </label>
                </div>
                <div class=\"button-row\">
                    <button type=\"button\" id=\"platform-load-strategy-health\">加载策略健康度</button>
                    <button type=\"button\" class=\"secondary\" id=\"platform-load-signal-summary\">加载信号摘要</button>
                    <button type=\"button\" class=\"secondary\" id=\"platform-load-analytics-overview\">加载策略总览</button>
                    <button type=\"button\" class=\"ghost\" id=\"platform-load-backtest-rankings\">加载回测排名</button>
                </div>
                <div class=\"status\" id=\"platform-strategy-status\"></div>
                <div class=\"table-wrap\" id=\"platform-strategy-view\"><div class=\"empty-state\">加载策略健康度、信号摘要、总览或回测排名后，这里会显示可读视图。</div></div>
                <pre class=\"json-output\" id=\"platform-strategy-output\"></pre>
            </div>
        </div>
        <div class=\"split-shell\">
            <div class=\"subpanel\">
                <h3>扫描器观测</h3>
                <p>直接从平台端查看 scanner 可观测摘要和实时决策，不再要求先进入 admin 再切回来做策略判断。</p>
                <div class=\"field-grid\">
                    <label>
                        运行状态
                        <select id=\"platform-scanner-status\">
                            <option value=\"\">全部</option>
                            <option value=\"running\">运行中</option>
                            <option value=\"completed\">已完成</option>
                            <option value=\"failed\">失败</option>
                        </select>
                    </label>
                    <label>
                        分桶 ID
                        <input id=\"platform-scanner-bucket-id\" type=\"number\" min=\"1\" placeholder=\"12\">
                    </label>
                    <label>
                        代码
                        <input id=\"platform-scanner-symbol\" type=\"text\" placeholder=\"AAPL\">
                    </label>
                    <label>
                        决策
                        <select id=\"platform-scanner-decision\">
                            <option value=\"\">全部</option>
                            <option value=\"emitted\">已发出</option>
                            <option value=\"suppressed\">已抑制</option>
                            <option value=\"skipped\">已跳过</option>
                            <option value=\"error\">错误</option>
                        </select>
                    </label>
                    <label>
                        运行上限
                        <input id=\"platform-scanner-limit\" type=\"number\" min=\"1\" max=\"200\" value=\"25\">
                    </label>
                    <label>
                        决策上限
                        <input id=\"platform-scanner-decision-limit\" type=\"number\" min=\"1\" max=\"200\" value=\"25\">
                    </label>
                </div>
                <div class=\"button-row\">
                    <button type=\"button\" id=\"platform-load-scanner-observability\">加载扫描器总览</button>
                    <button type=\"button\" class=\"secondary\" id=\"platform-load-scanner-live-decisions\">加载实时决策</button>
                </div>
                <div class=\"status\" id=\"platform-scanner-status-output\"></div>
                <div class=\"table-wrap\" id=\"platform-scanner-view\"><div class=\"empty-state\">加载扫描器总览或实时决策后，这里会显示运行摘要和决策表。</div></div>
                <pre class=\"json-output\" id=\"platform-scanner-output\"></pre>
            </div>
            <div class=\"subpanel\">
                <h3>回测实验</h3>
                <p>回测运行、排名刷新和策略筛选都收口到这里，作为桌面端实验链路的一部分持续使用。</p>
                <div class=\"field-grid\">
                    <label>
                        运行状态
                        <select id=\"platform-backtests-status\">
                            <option value=\"\">全部</option>
                            <option value=\"pending\">待处理</option>
                            <option value=\"running\">运行中</option>
                            <option value=\"completed\">已完成</option>
                            <option value=\"failed\">失败</option>
                        </select>
                    </label>
                    <label>
                        策略名
                        <input id=\"platform-backtests-strategy\" type=\"text\" placeholder=\"momentum\">
                    </label>
                    <label>
                        周期
                        <input id=\"platform-backtests-timeframe\" type=\"text\" value=\"1d\" placeholder=\"1d\">
                    </label>
                    <label>
                        标的
                        <input id=\"platform-backtests-symbol\" type=\"text\" placeholder=\"AAPL\">
                    </label>
                    <label>
                        运行上限
                        <input id=\"platform-backtests-limit\" type=\"number\" min=\"1\" max=\"200\" value=\"25\">
                    </label>
                    <label>
                        刷新窗口
                        <input id=\"platform-backtests-refresh-windows\" type=\"text\" placeholder=\"30, 90, 180\">
                    </label>
                </div>
                <div class=\"field-grid\">
                    <label>
                        刷新标的（逗号分隔）
                        <input id=\"platform-backtests-refresh-symbols\" type=\"text\" placeholder=\"AAPL, MSFT\">
                    </label>
                    <label>
                        刷新策略（逗号分隔）
                        <input id=\"platform-backtests-refresh-strategies\" type=\"text\" placeholder=\"momentum, mean-reversion\">
                    </label>
                </div>
                <div class=\"field-grid\">
                    <label>
                        高权限确认
                        <span>只有在确认需要立即刷新实验排名时才勾选，避免误触触发整批回测。</span>
                        <input id=\"platform-backtests-refresh-confirm\" type=\"checkbox\">
                    </label>
                </div>
                <div class=\"button-row\">
                    <button type=\"button\" id=\"platform-load-backtest-runs\">加载回测运行</button>
                    <button type=\"button\" class=\"secondary\" id=\"platform-trigger-backtest-refresh\">触发排名刷新</button>
                </div>
                <div class=\"status\" id=\"platform-backtests-status-output\"></div>
                <div class=\"table-wrap\" id=\"platform-backtests-view\"><div class=\"empty-state\">加载回测运行或触发实验后，这里会显示运行列表与结果摘要。</div></div>
                <pre class=\"json-output\" id=\"platform-backtests-output\"></pre>
            </div>
        </div>
        <div class=\"subpanel\">
            <h3>底层接口调试台</h3>
            <p>如果预设动作还不够，再退回到端点级调试；这里同时覆盖 public API 与高权限策略接口。</p>
            <form id=\"platform-endpoint-console-form\">
                <div class=\"field-grid\">
                    <label>
                        端点
                        <select id=\"platform-endpoint-select\"></select>
                    </label>
                    <label>
                        Bearer Token 覆盖（可选）
                        <input id=\"platform-endpoint-token\" type=\"text\" placeholder=\"留空时按端点配置自动处理认证\">
                    </label>
                </div>
                <div class=\"field-grid\">
                    <label>
                        路径参数 JSON（可选）
                        <textarea id=\"platform-endpoint-path-params\" placeholder='{"item_id": 1}'></textarea>
                    </label>
                    <label>
                        查询参数 JSON（可选）
                        <textarea id=\"platform-endpoint-query-params\" placeholder='{"q": "AAPL", "limit": 20}'></textarea>
                    </label>
                </div>
                <div class=\"field-grid\">
                    <label>
                        请求体 JSON（可选）
                        <textarea id=\"platform-endpoint-body\" placeholder='{"symbol": "AAPL"}'></textarea>
                    </label>
                    <label>
                        附加请求头 JSON（可选）
                        <textarea id=\"platform-endpoint-headers\" placeholder='{"X-Custom-Header": "value"}'></textarea>
                    </label>
                </div>
                <div class=\"button-row\">
                    <button type=\"submit\">执行选中端点</button>
                    <button type=\"button\" class=\"secondary\" id=\"platform-endpoint-reset\">重置调试台</button>
                </div>
            </form>
            <div class=\"status\" id=\"platform-endpoint-console-status\"></div>
            <pre class=\"json-output\" id=\"platform-endpoint-output\"></pre>
        </div>
    </div>
</section>
"""

_ADMIN_BODY = """
<section class=\"panel wide admin-overview\" id=\"admin-overview\">
    <div class=\"panel-header\">
        <div>
            <h2>运营治理总览</h2>
            <p class=\"panel-copy\">next/admin 聚焦用户、推送、权限、审计与运行治理。策略相关页只作为内部高权限观测面存在，不再把 admin 写成策略产品中心。</p>
        </div>
        <span class=\"pill\">运营治理面</span>
    </div>
    <div class=\"ops-grid\">
        <article class=\"ops-card\">
            <small>Lane 01</small>
            <strong>用户与订阅</strong>
            <span>用户资料、订阅状态、套餐调整和生命周期管理属于 admin 主责。</span>
        </article>
        <article class=\"ops-card\">
            <small>Lane 02</small>
            <strong>推送与消息</strong>
            <span>手动分发、发件箱、回执和消息任务组成运营主链路。</span>
        </article>
        <article class=\"ops-card\">
            <small>Lane 03</small>
            <strong>权限与审计</strong>
            <span>管理员身份、操作员范围和操作留痕用于控制谁能做什么。</span>
        </article>
        <article class=\"ops-card\">
            <small>Lane 04</small>
            <strong>监控与发布</strong>
            <span>运行态、告警、验收和发布证据是治理主责；策略运行页仅作内部观测。</span>
        </article>
    </div>
    <div class=\"section-nav\">
        <a class=\"section-link\" href=\"#admin-auth\">身份权限</a>
        <a class=\"section-link\" href=\"#admin-users\">用户订阅</a>
        <a class=\"section-link\" href=\"#admin-distribution\">推送任务</a>
        <a class=\"section-link\" href=\"#admin-runtime\">监控治理</a>
        <a class=\"section-link\" href=\"#admin-scanner\">内部策略观测</a>
    </div>
</section>
""" + _BASE_CONNECTION_PANEL + """
<section class=\"panel span-8\" id=\"admin-auth\">
    <div class=\"panel-header\">
        <div>
            <h2>身份与权限</h2>
            <p class=\"panel-copy\">把登录、验证、Token 覆盖和 operator 标识收口到同一权限域里，先确认是谁在操作，再去执行用户、推送或治理动作。</p>
        </div>
        <span class=\"pill\">身份控制</span>
    </div>
    <div class=\"split-shell\">
        <div class=\"stack-flow\">
            <div class=\"subpanel\">
                <h3>发送管理验证码</h3>
                <p>仅保留最短登录链路，适合管理员在值班切换或新设备接入时快速拿到会话。</p>
                <form id=\"admin-send-code-form\">
                    <div class=\"field-grid single\">
                        <label>
                            管理员邮箱
                            <input id=\"admin-auth-email\" type=\"email\" placeholder=\"admin@example.com\" required>
                        </label>
                    </div>
                    <div class=\"button-row\">
                        <button type=\"submit\">发送管理验证码</button>
                    </div>
                </form>
            </div>
            <div class=\"subpanel\">
                <h3>验证并保留会话</h3>
                <p>刷新、退出和登录后的状态反馈都保持在同一个会话卡里，避免后台运维误用旧 Token。</p>
                <form id=\"admin-verify-form\">
                    <div class=\"field-grid\">
                        <label>
                            验证邮箱
                            <input id=\"admin-verify-email\" type=\"email\" placeholder=\"admin@example.com\" required>
                        </label>
                        <label>
                            6 位验证码
                            <input id=\"admin-verify-code\" type=\"text\" maxlength=\"6\" placeholder=\"123456\" required>
                        </label>
                        <label>
                            语言地区
                            <input id=\"admin-verify-locale\" type=\"text\" placeholder=\"zh-CN\">
                        </label>
                        <label>
                            时区
                            <input id=\"admin-verify-timezone\" type=\"text\" placeholder=\"Asia/Shanghai\">
                        </label>
                    </div>
                    <div class=\"button-row\">
                        <button type=\"submit\">验证并保存管理会话</button>
                        <button type=\"button\" class=\"secondary\" id=\"refresh-admin-session\">刷新管理令牌</button>
                        <button type=\"button\" class=\"ghost\" id=\"logout-admin-session\">退出管理会话</button>
                    </div>
                </form>
                <div class=\"status\" id=\"admin-auth-status\"></div>
                <pre class=\"json-output\" id=\"admin-auth-output\"></pre>
            </div>
        </div>
        <div class=\"stack-flow\">
            <div class=\"subpanel\">
                <h3>值班身份与令牌覆盖</h3>
                <p>保留手动 Token 覆盖和 operator ID，便于代理验证、紧急回放和多角色切换。</p>
                <div class=\"field-grid single\">
                    <label>
                        手动覆盖管理访问令牌
                        <textarea id=\"admin-token\" placeholder=\"在此粘贴 Bearer Token\"></textarea>
                    </label>
                </div>
                <div class=\"field-grid single\">
                    <label>
                        操作员 ID 覆盖
                        <input id=\"admin-operator-id\" type=\"number\" min=\"1\" placeholder=\"7\">
                    </label>
                </div>
                <div class=\"button-row\">
                    <button type=\"button\" id=\"save-admin-token\">保存粘贴的令牌</button>
                    <button type=\"button\" class=\"secondary\" id=\"show-admin-session\">查看管理会话</button>
                    <button type=\"button\" class=\"ghost\" id=\"clear-admin-session\">清除管理会话</button>
                </div>
            </div>
            <div class=\"subpanel\">
                <h3>当前班次提示</h3>
                <p>后台值班时建议先确认当前会话、operator ID 和 Token 来源，再执行任务领取或用户变更。</p>
                <ul class=\"micro-list\">
                    <li>如果通过验证码登录，优先使用自动保存的本地会话，避免手工粘贴旧 Token。</li>
                    <li>如果通过代理或调试环境接入，手动 Token 覆盖和 operator ID 可以明确当前权限上下文。</li>
                    <li>执行用户、任务或发布动作前，可先点“查看管理会话”确认当前身份。</li>
                </ul>
                <div class=\"status\" id=\"admin-session-status\"></div>
                <pre class=\"json-output\" id=\"admin-session-output\"></pre>
            </div>
        </div>
    </div>
</section>

<section class=\"panel span-6\" id=\"admin-operators\">
    <div class=\"panel-header\">
        <div>
            <h2>操作员与权限范围</h2>
            <p class=\"panel-copy\">这里管理谁能做什么，而不是在管理端里直接做策略研究。</p>
        </div>
        <span class=\"pill\">/v1/admin/operators</span>
    </div>
    <div class=\"field-grid\">
        <label>
                查询
                <input id=\"admin-operators-query\" type=\"text\" placeholder=\"邮箱或姓名\">
        </label>
        <label>
            角色筛选
            <select id=\"admin-operators-role\">
                <option value=\"\">任意角色</option>
                <option value=\"viewer\">查看者</option>
                <option value=\"operator\">操作员</option>
                <option value=\"admin\">管理员</option>
            </select>
        </label>
        <label>
            启用状态筛选
            <select id=\"admin-operators-active\">
                <option value=\"\">任意状态</option>
                <option value=\"true\">启用</option>
                <option value=\"false\">停用</option>
            </select>
        </label>
        <label>
            数量上限
            <input id=\"admin-operators-limit\" type=\"number\" min=\"1\" max=\"200\" value=\"25\">
        </label>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" id=\"load-operators\">加载操作员</button>
    </div>
    <form id=\"upsert-operator-form\">
        <div class=\"field-grid\">
            <label>
                用户 ID
                <input id=\"admin-operator-user-id\" type=\"number\" min=\"1\" placeholder=\"7\" required>
            </label>
            <label>
                新角色
                <select id=\"admin-operator-role\">
                    <option value=\"\">保持当前</option>
                    <option value=\"viewer\">查看者</option>
                    <option value=\"operator\">操作员</option>
                    <option value=\"admin\">管理员</option>
                </select>
            </label>
            <label>
                启用状态
                <select id=\"admin-operator-is-active\">
                    <option value=\"\">保持当前</option>
                    <option value=\"true\">启用</option>
                    <option value=\"false\">停用</option>
                </select>
            </label>
            <label>
                权限范围
                <input id=\"admin-operator-scopes\" type=\"text\" placeholder=\"runtime, analytics, distribution\">
            </label>
        </div>
        <div class=\"button-row\">
            <button type=\"submit\" class=\"secondary\">写入操作员</button>
        </div>
    </form>
    <div class=\"status\" id=\"admin-operators-status\"></div>
    <pre class=\"json-output\" id=\"admin-operators-output\"></pre>
</section>

<section class=\"panel span-6\" id=\"admin-distribution\">
    <div class=\"panel-header\">
        <div>
            <h2>推送与手动分发</h2>
            <p class=\"panel-copy\">管理端的主责之一是消息运营。这里用于排入手动邮件、推送和服务通知，不承载策略本身。</p>
        </div>
        <span class=\"pill\">/v1/admin/distribution/manual-message</span>
    </div>
    <form id=\"manual-distribution-form\">
        <div class=\"field-grid\">
            <label>
                用户 ID 列表
                <input id=\"distribution-user-ids\" type=\"text\" placeholder=\"7, 12, 19\" required>
            </label>
            <label>
                通知类型
                <input id=\"distribution-type\" type=\"text\" placeholder=\"manual.message\" value=\"manual.message\">
            </label>
            <label>
                确认截止时间（可选）
                <input id=\"distribution-ack-deadline\" type=\"text\" placeholder=\"2026-04-06T12:00:00+08:00\">
            </label>
            <label>
                标题
                <input id=\"distribution-title\" type=\"text\" placeholder=\"服务通知\" required>
            </label>
        </div>
        <label>
            正文
            <textarea id=\"distribution-body\" placeholder=\"消息正文\" required></textarea>
        </label>
        <label>
            元数据 JSON（可选）
            <textarea id=\"distribution-metadata\" placeholder='{\"campaign\":\"cutover-check\"}'></textarea>
        </label>
        <div class=\"button-row\">
            <label class=\"inline-check\">
                <input id=\"distribution-channel-email\" type=\"checkbox\" checked>
                邮件
            </label>
            <label class=\"inline-check\">
                <input id=\"distribution-channel-push\" type=\"checkbox\" checked>
                推送
            </label>
            <label class=\"inline-check\">
                <input id=\"distribution-ack-required\" type=\"checkbox\">
                需要确认
            </label>
            <button type=\"submit\">排入手动消息</button>
        </div>
    </form>
    <div class=\"status\" id=\"admin-distribution-status\"></div>
    <pre class=\"json-output\" id=\"admin-distribution-output\"></pre>
</section>

<section class=\"panel span-8\" id=\"admin-receipts\">
    <div class=\"panel-header\">
        <div>
            <h2>消息回执任务</h2>
            <p class=\"panel-copy\">围绕需要确认的消息、超时跟进和人工领取建立运营任务链路。</p>
        </div>
        <span class=\"pill\">/v1/admin/tasks/receipts*</span>
    </div>
    <div class=\"field-grid\">
        <label>
            跟进状态
            <select id=\"task-receipts-follow-up-status\">
                <option value=\"\">全部</option>
                <option value=\"none\">无</option>
                <option value=\"pending\">待处理</option>
                <option value=\"claimed\">已领取</option>
                <option value=\"resolved\">已解决</option>
            </select>
        </label>
        <label>
            发送状态
            <select id=\"task-receipts-delivery-status\">
                <option value=\"\">全部</option>
                <option value=\"pending\">待处理</option>
                <option value=\"delivered\">已送达</option>
                <option value=\"failed\">失败</option>
            </select>
        </label>
        <label>
            需要确认
            <select id=\"task-receipts-ack-required\">
                <option value=\"\">全部</option>
                <option value=\"true\">需要</option>
                <option value=\"false\">不需要</option>
            </select>
        </label>
        <label>
            用户 ID
            <input id=\"task-receipts-user-id\" type=\"number\" min=\"1\" placeholder=\"42\">
        </label>
        <label>
            通知 ID
            <input id=\"task-receipts-notification-id\" type=\"text\" placeholder=\"notification-123\">
        </label>
        <label>
            数量上限
            <input id=\"task-receipts-limit\" type=\"number\" min=\"1\" max=\"200\" value=\"25\">
        </label>
    </div>
    <div class=\"button-row\">
        <label class=\"inline-check\">
            <input id=\"task-receipts-overdue-only\" type=\"checkbox\">
            仅超时
        </label>
        <button type=\"button\" id=\"load-task-receipts\">加载回执</button>
        <button type=\"button\" class=\"secondary\" id=\"escalate-task-receipts\">升级超时项</button>
    </div>
    <div class=\"field-grid single\">
        <label>
            用于确认、领取或解决的回执 ID
            <input id=\"task-receipt-id\" type=\"text\" placeholder=\"receipt-123\">
        </label>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" class=\"secondary\" id=\"ack-task-receipt\">确认回执</button>
        <button type=\"button\" class=\"secondary\" id=\"claim-task-receipt\">领取跟进</button>
        <button type=\"button\" class=\"ghost\" id=\"resolve-task-receipt\">解决跟进</button>
    </div>
    <div class=\"status\" id=\"admin-task-receipts-status\"></div>
    <pre class=\"json-output\" id=\"admin-task-receipts-output\"></pre>
</section>

<section class=\"panel span-4\" id=\"admin-outbox\">
    <div class=\"panel-header\">
        <div>
            <h2>消息发件箱</h2>
            <p class=\"panel-copy\">查看待投递消息、释放过期 processing 行，并重新入队发件箱记录。</p>
        </div>
        <span class=\"pill\">/v1/admin/tasks/outbox*</span>
    </div>
    <div class=\"field-grid\">
        <label>
            渠道
            <select id=\"task-outbox-channel\">
                <option value=\"\">全部</option>
                <option value=\"email\">邮件</option>
                <option value=\"push\">推送</option>
            </select>
        </label>
        <label>
            状态
            <select id=\"task-outbox-status\">
                <option value=\"\">全部</option>
                <option value=\"pending\">待处理</option>
                <option value=\"processing\">处理中</option>
                <option value=\"delivered\">已送达</option>
                <option value=\"failed\">失败</option>
            </select>
        </label>
        <label>
            用户 ID
            <input id=\"task-outbox-user-id\" type=\"number\" min=\"1\" placeholder=\"42\">
        </label>
        <label>
            通知 ID
            <input id=\"task-outbox-notification-id\" type=\"text\" placeholder=\"notification-123\">
        </label>
        <label>
            数量上限
            <input id=\"task-outbox-limit\" type=\"number\" min=\"1\" max=\"200\" value=\"25\">
        </label>
        <label>
            释放早于此时间（分钟）
            <input id=\"task-outbox-older-minutes\" type=\"number\" min=\"1\" max=\"1440\" value=\"15\">
        </label>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" id=\"load-task-outbox\">加载发件箱</button>
        <button type=\"button\" class=\"secondary\" id=\"release-task-outbox\">释放陈旧任务</button>
    </div>
    <div class=\"field-grid\">
        <label>
            单个发件箱 ID
            <input id=\"task-outbox-id\" type=\"text\" placeholder=\"outbox-123\">
        </label>
        <label>
            多个发件箱 ID
            <input id=\"task-outbox-ids\" type=\"text\" placeholder=\"outbox-1, outbox-2\">
        </label>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" class=\"secondary\" id=\"requeue-task-outbox\">单条重新入队</button>
        <button type=\"button\" class=\"ghost\" id=\"retry-task-outbox\">重试所选</button>
    </div>
    <div class=\"status\" id=\"admin-task-outbox-status\"></div>
    <pre class=\"json-output\" id=\"admin-task-outbox-output\"></pre>
</section>

<section class=\"panel span-4\" id=\"admin-trades\">
    <div class=\"panel-header\">
        <div>
            <h2>交易复核任务</h2>
            <p class=\"panel-copy\">这里只处理人工领取、复核或过期等治理动作，不把管理端写成策略执行主界面。</p>
        </div>
        <span class=\"pill\">/v1/admin/tasks/trades*</span>
    </div>
    <div class=\"field-grid\">
        <label>
            状态
            <select id=\"task-trades-status\">
                <option value=\"\">全部</option>
                <option value=\"pending\">待处理</option>
                <option value=\"confirmed\">已确认</option>
                <option value=\"adjusted\">已调整</option>
                <option value=\"ignored\">已忽略</option>
                <option value=\"expired\">已过期</option>
            </select>
        </label>
        <label>
            动作
            <select id=\"task-trades-action\">
                <option value=\"\">全部</option>
                <option value=\"buy\">买入</option>
                <option value=\"sell\">卖出</option>
                <option value=\"add\">加仓</option>
            </select>
        </label>
        <label>
            被哪个操作员领取
            <input id=\"task-trades-claimed-by\" type=\"number\" min=\"1\" placeholder=\"7\">
        </label>
        <label>
            用户 ID
            <input id=\"task-trades-user-id\" type=\"number\" min=\"1\" placeholder=\"42\">
        </label>
        <label>
            代码
            <input id=\"task-trades-symbol\" type=\"text\" placeholder=\"AAPL\">
        </label>
        <label>
            数量上限
            <input id=\"task-trades-limit\" type=\"number\" min=\"1\" max=\"200\" value=\"25\">
        </label>
    </div>
    <div class=\"button-row\">
        <label class=\"inline-check\">
            <input id=\"task-trades-expired-only\" type=\"checkbox\">
            仅已过期
        </label>
        <label class=\"inline-check\">
            <input id=\"task-trades-claimed-only\" type=\"checkbox\">
            仅已领取
        </label>
        <button type=\"button\" id=\"load-task-trades\">加载交易任务</button>
    </div>
    <div class=\"field-grid single\">
        <label>
            批量操作的交易 ID（可选）
            <input id=\"task-trades-ids\" type=\"text\" placeholder=\"trade-1, trade-2\">
        </label>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" class=\"secondary\" id=\"claim-task-trades\">领取交易</button>
        <button type=\"button\" class=\"ghost\" id=\"expire-task-trades\">设为过期</button>
    </div>
    <div class=\"status\" id=\"admin-task-trades-status\"></div>
    <pre class=\"json-output\" id=\"admin-task-trades-output\"></pre>
</section>

<section class=\"panel span-7\" id=\"admin-users\">
    <div class=\"panel-header\">
        <div>
            <h2>用户与订阅</h2>
            <p class=\"panel-copy\">加载用户记录、查看订阅状态、更新资料或资金字段，并执行批量套餐或启用状态调整。</p>
        </div>
        <span class=\"pill\">/v1/admin/users*</span>
    </div>
    <div class=\"field-grid\">
        <label>
            查询
            <input id=\"admin-users-query\" type=\"text\" placeholder=\"邮箱或姓名\">
        </label>
        <label>
            套餐
            <input id=\"admin-users-plan\" type=\"text\" placeholder=\"free, pro, enterprise\">
        </label>
        <label>
            启用状态
            <select id=\"admin-users-active\">
                <option value=\"\">全部</option>
                <option value=\"true\">启用</option>
                <option value=\"false\">停用</option>
            </select>
        </label>
        <label>
            数量上限
            <input id=\"admin-users-limit\" type=\"number\" min=\"1\" max=\"200\" value=\"25\">
        </label>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" id=\"load-admin-users\">加载用户</button>
    </div>
    <form id=\"update-admin-user-form\">
        <div class=\"field-grid\">
            <label>
                用户 ID
                <input id=\"admin-user-id\" type=\"number\" min=\"1\" placeholder=\"42\" required>
            </label>
            <label>
                姓名
                <input id=\"admin-user-name\" type=\"text\" placeholder=\"张三\">
            </label>
            <label>
                套餐
                <input id=\"admin-user-plan\" type=\"text\" placeholder=\"pro\">
            </label>
            <label>
                语言地区
                <input id=\"admin-user-locale\" type=\"text\" placeholder=\"zh-CN\">
            </label>
            <label>
                时区
                <input id=\"admin-user-timezone\" type=\"text\" placeholder=\"Asia/Shanghai\">
            </label>
            <label>
                币种
                <input id=\"admin-user-currency\" type=\"text\" placeholder=\"USD\">
            </label>
            <label>
                总资金
                <input id=\"admin-user-total-capital\" type=\"number\" step=\"0.01\" min=\"0.01\" placeholder=\"100000\">
            </label>
            <label>
                启用状态
                <select id=\"admin-user-is-active\">
                    <option value=\"\">保持当前</option>
                    <option value=\"true\">启用</option>
                    <option value=\"false\">停用</option>
                </select>
            </label>
        </div>
        <label>
            附加 JSON
            <textarea id=\"admin-user-extra\" placeholder='{"subscription":{"status":"active"}}'></textarea>
        </label>
        <div class=\"button-row\">
            <button type=\"button\" class=\"secondary\" id=\"load-admin-user-detail\">加载用户详情</button>
            <button type=\"submit\">更新用户</button>
        </div>
    </form>
    <form id=\"bulk-update-users-form\">
        <div class=\"field-grid\">
            <label>
                用户 ID 列表
                <input id=\"admin-bulk-user-ids\" type=\"text\" placeholder=\"42, 43, 44\" required>
            </label>
            <label>
                批量套餐
                <input id=\"admin-bulk-user-plan\" type=\"text\" placeholder=\"enterprise\">
            </label>
            <label>
                批量启用状态
                <select id=\"admin-bulk-user-active\">
                    <option value=\"\">不变</option>
                    <option value=\"true\">启用</option>
                    <option value=\"false\">停用</option>
                </select>
            </label>
        </div>
        <div class=\"button-row\">
            <button type=\"submit\" class=\"secondary\">批量更新用户</button>
        </div>
    </form>
    <div class=\"status\" id=\"admin-users-status\"></div>
    <pre class=\"json-output\" id=\"admin-users-output\"></pre>
</section>

<section class=\"panel span-5\" id=\"admin-audit\">
    <div class=\"panel-header\">
        <div>
            <h2>审计与操作留痕</h2>
            <p class=\"panel-copy\">按实体、动作、来源、请求 ID 或发件箱状态筛选审计事件，确认高风险动作的责任归属。</p>
        </div>
        <span class=\"pill\">/v1/admin/audit</span>
    </div>
    <div class=\"field-grid\">
        <label>
            实体
            <input id=\"admin-audit-entity\" type=\"text\" placeholder=\"trade\">
        </label>
        <label>
            实体 ID
            <input id=\"admin-audit-entity-id\" type=\"text\" placeholder=\"trade-123\">
        </label>
        <label>
            动作
            <input id=\"admin-audit-action\" type=\"text\" placeholder=\"tasks.claimed\">
        </label>
        <label>
            来源
            <input id=\"admin-audit-source\" type=\"text\" placeholder=\"admin-api\">
        </label>
        <label>
            状态
            <select id=\"admin-audit-status\">
                <option value=\"\">全部</option>
                <option value=\"pending\">待处理</option>
                <option value=\"published\">已发布</option>
            </select>
        </label>
        <label>
            请求 ID
            <input id=\"admin-audit-request-id\" type=\"text\" placeholder=\"request-id\">
        </label>
        <label>
            数量上限
            <input id=\"admin-audit-limit\" type=\"number\" min=\"1\" max=\"200\" value=\"25\">
        </label>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" id=\"load-admin-audit\">加载审计事件</button>
    </div>
    <div class=\"status\" id=\"admin-audit-status\"></div>
    <pre class=\"json-output\" id=\"admin-audit-output\"></pre>
</section>

<section class=\"panel span-7\" id=\"admin-scanner\">
    <div class=\"panel-header\">
        <div>
            <h2>内部策略观测：扫描器</h2>
            <p class=\"panel-copy\">这里用于治理和值班时观测平台策略运行，不意味着 scanner 属于 admin 的产品中心。</p>
        </div>
        <span class=\"pill\">/v1/admin/scanner/*</span>
    </div>
    <div class=\"field-grid\">
        <label>
            运行状态
            <select id=\"admin-scanner-status\">
                <option value=\"\">全部</option>
                <option value=\"running\">运行中</option>
                <option value=\"completed\">已完成</option>
                <option value=\"failed\">失败</option>
            </select>
        </label>
        <label>
            分桶 ID
            <input id=\"admin-scanner-bucket-id\" type=\"number\" min=\"1\" placeholder=\"12\">
        </label>
        <label>
            代码
            <input id=\"admin-scanner-symbol\" type=\"text\" placeholder=\"AAPL\">
        </label>
        <label>
            决策
            <select id=\"admin-scanner-decision\">
                <option value=\"\">全部</option>
                <option value=\"emitted\">已发出</option>
                <option value=\"suppressed\">已抑制</option>
                <option value=\"skipped\">已跳过</option>
                <option value=\"error\">错误</option>
            </select>
        </label>
        <label>
            运行数量上限
            <input id=\"admin-scanner-limit\" type=\"number\" min=\"1\" max=\"200\" value=\"25\">
        </label>
        <label>
            决策数量上限
            <input id=\"admin-scanner-decision-limit\" type=\"number\" min=\"1\" max=\"200\" value=\"25\">
        </label>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" id=\"load-scanner-observability\">加载可观测数据</button>
    </div>
    <div class=\"field-grid\">
        <label>
            运行 ID
            <input id=\"admin-scanner-run-id\" type=\"number\" min=\"1\" placeholder=\"101\">
        </label>
        <label>
            单次运行决策上限
            <input id=\"admin-scanner-run-decision-limit\" type=\"number\" min=\"1\" max=\"500\" value=\"100\">
        </label>
        <label>
            实时代码
            <input id=\"admin-scanner-live-symbol\" type=\"text\" placeholder=\"AAPL\">
        </label>
        <label>
            实时决策
            <select id=\"admin-scanner-live-decision\">
                <option value=\"\">全部</option>
                <option value=\"emitted\">已发出</option>
                <option value=\"suppressed\">已抑制</option>
                <option value=\"skipped\">已跳过</option>
                <option value=\"error\">错误</option>
            </select>
        </label>
        <label>
            已抑制
            <select id=\"admin-scanner-live-suppressed\">
                <option value=\"\">全部</option>
                <option value=\"true\">是</option>
                <option value=\"false\">否</option>
            </select>
        </label>
        <label>
            实时数量上限
            <input id=\"admin-scanner-live-limit\" type=\"number\" min=\"1\" max=\"200\" value=\"25\">
        </label>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" class=\"secondary\" id=\"load-scanner-run\">加载运行详情</button>
        <button type=\"button\" class=\"ghost\" id=\"load-scanner-live-decisions\">加载实时决策</button>
    </div>
    <div class=\"status\" id=\"admin-scanner-status-output\"></div>
    <pre class=\"json-output\" id=\"admin-scanner-output\"></pre>
</section>

<section class=\"panel span-5\" id=\"admin-backtests\">
    <div class=\"panel-header\">
        <div>
            <h2>内部策略观测：回测</h2>
            <p class=\"panel-copy\">用于查看平台策略实验、排名刷新和运行记录；从产品归属上，这些能力仍属于平台核心。</p>
        </div>
        <span class=\"pill\">/v1/admin/backtests/*</span>
    </div>
    <div class=\"field-grid\">
        <label>
            运行状态
            <select id=\"admin-backtests-status\">
                <option value=\"\">全部</option>
                <option value=\"pending\">待处理</option>
                <option value=\"running\">运行中</option>
                <option value=\"completed\">已完成</option>
                <option value=\"failed\">失败</option>
            </select>
        </label>
        <label>
            策略
            <input id=\"admin-backtests-strategy\" type=\"text\" placeholder=\"momentum\">
        </label>
        <label>
            周期
            <input id=\"admin-backtests-timeframe\" type=\"text\" placeholder=\"1d\">
        </label>
        <label>
            代码
            <input id=\"admin-backtests-symbol\" type=\"text\" placeholder=\"AAPL\">
        </label>
        <label>
            数量上限
            <input id=\"admin-backtests-limit\" type=\"number\" min=\"1\" max=\"200\" value=\"25\">
        </label>
        <label>
            运行 ID
            <input id=\"admin-backtest-run-id\" type=\"number\" min=\"1\" placeholder=\"18\">
        </label>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" id=\"load-backtest-runs\">加载运行记录</button>
        <button type=\"button\" class=\"secondary\" id=\"load-backtest-run\">加载运行详情</button>
    </div>
    <div class=\"field-grid\">
        <label>
            排名周期
            <input id=\"admin-backtests-rankings-timeframe\" type=\"text\" placeholder=\"1d\">
        </label>
        <label>
            排名数量上限
            <input id=\"admin-backtests-rankings-limit\" type=\"number\" min=\"1\" max=\"100\" value=\"20\">
        </label>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" class=\"secondary\" id=\"load-backtest-rankings\">加载最新排名</button>
    </div>
    <form id=\"trigger-backtest-refresh-form\">
        <div class=\"field-grid\">
            <label>
                标的列表
                <input id=\"admin-backtests-refresh-symbols\" type=\"text\" placeholder=\"AAPL, MSFT\">
            </label>
            <label>
                策略名称
                <input id=\"admin-backtests-refresh-strategies\" type=\"text\" placeholder=\"momentum, mean-reversion\">
            </label>
            <label>
                窗口参数
                <input id=\"admin-backtests-refresh-windows\" type=\"text\" placeholder=\"30, 90, 180\">
            </label>
            <label>
                刷新周期
                <input id=\"admin-backtests-refresh-timeframe\" type=\"text\" value=\"1d\">
            </label>
        </div>
        <div class=\"button-row\">
            <button type=\"submit\" class=\"ghost\">触发排名刷新</button>
        </div>
    </form>
    <div class=\"status\" id=\"admin-backtests-status-output\"></div>
    <pre class=\"json-output\" id=\"admin-backtests-output\"></pre>
</section>

<section class=\"panel span-4\" id=\"admin-analytics\">
    <div class=\"panel-header\">
        <div>
            <h2>平台运行分析</h2>
            <p class=\"panel-copy\">从治理与复核视角查看分发、策略健康度和 TradingAgents 读模型，而不是把 admin 变成策略驾驶舱。</p>
        </div>
        <span class=\"pill\">/v1/admin/analytics/*</span>
    </div>
    <div class=\"field-grid single\">
        <label>
            时间窗口（小时）
            <input id=\"admin-window-hours\" type=\"number\" min=\"1\" max=\"720\" value=\"24\">
        </label>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" id=\"load-overview\">加载总览</button>
        <button type=\"button\" class=\"secondary\" id=\"load-distribution\">加载分发数据</button>
        <button type=\"button\" class=\"secondary\" id=\"load-strategy-health\">加载策略健康度</button>
        <button type=\"button\" class=\"ghost\" id=\"load-tradingagents\">加载 TradingAgents</button>
    </div>
    <div class=\"status\" id=\"admin-analytics-status\"></div>
    <pre class=\"json-output\" id=\"admin-analytics-output\"></pre>
</section>

<section class=\"panel span-4\" id=\"admin-runtime\">
    <div class=\"panel-header\">
        <div>
            <h2>运行监控</h2>
            <p class=\"panel-copy\">查看 admin API 与相关组件健康、运行指标和当前告警状态，这是管理端最核心的治理能力之一。</p>
        </div>
        <span class=\"pill\">/v1/admin/runtime/*</span>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" id=\"load-runtime-health\">加载健康状态</button>
        <button type=\"button\" class=\"secondary\" id=\"load-runtime-metrics\">加载指标</button>
        <button type=\"button\" class=\"ghost\" id=\"load-runtime-alerts\">加载告警</button>
    </div>
    <div class=\"status\" id=\"admin-runtime-status\"></div>
    <pre class=\"json-output\" id=\"admin-runtime-output\"></pre>
</section>

<section class=\"panel span-4\" id=\"admin-acceptance\">
    <div class=\"panel-header\">
        <div>
            <h2>验收与发布治理</h2>
            <p class=\"panel-copy\">拉取就绪度报告与制品清单，用于切换、验收与变更治理。</p>
        </div>
        <span class=\"pill\">/v1/admin/acceptance/*</span>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" id=\"load-acceptance-status\">加载验收状态</button>
        <button type=\"button\" class=\"secondary\" id=\"load-acceptance-report\">加载验收报告</button>
    </div>
    <div class=\"status\" id=\"admin-acceptance-status\"></div>
    <pre class=\"json-output\" id=\"admin-acceptance-output\"></pre>
</section>
"""


def _render_hero_stats(stats: list[tuple[str, str]]) -> str:
    return "".join(
        f'<div class="hero-stat"><strong>{escape(title)}</strong><span>{escape(copy)}</span></div>'
        for title, copy in stats
    )


def _render_hero_aside_items(items: list[str]) -> str:
    return "".join(f"<li>{escape(item)}</li>" for item in items)

_PAGE_META = {
    "app": {
        "title": "订阅端",
        "hero_title": "像正式移动投资产品一样，先整理账户与资产，再一次性启动订阅。",
        "hero_copy": "next/app 现在强调窄屏流程、单用户资产录入和离线优先草稿。用户可以像使用成熟移动券商一样，先准备 watchlist、持仓和现金，再把本次监控快照同步到服务端。",
        "hero_stats": [
            ("离线优先草稿", "订阅股票、持仓和现金先保存在当前设备。"),
            ("一步启动同步", "准备好后再用一次主动作把快照写入服务端。"),
            ("轻交互登录", "邮箱验证码即可完成登录、刷新和恢复云端资料。"),
        ],
        "hero_aside_title": "移动产品原则",
        "hero_aside_items": [
            "单页完成关键录入，减少在移动端多层跳转。",
            "把最关键的资产数据放在主路径里，不依赖隐藏设置。",
            "同步动作集中到一个主按钮，避免误触发多次写入。",
            "右侧设备卡片持续反馈当前会话和同步结果。",
        ],
        "body": _APP_BODY,
        "script": _APP_SCRIPT,
    },
    "platform": {
        "title": "平台端",
        "hero_title": "平台才是策略核心：买入预警、退出规则、回测与胜率都应在这里闭环。",
        "hero_copy": "next/platform 继续运行在 public API 之上，但职责被重新收束为桌面策略核心。候选标的、策略观察池、退出参数、交易执行以及内部高权限策略接口都应围绕同一套桌面工作流组织。",
        "hero_stats": [
            ("买入策略", "候选标的、观察池和入场信号应在平台端形成统一工作流。"),
            ("退出策略", "持仓、止盈止损和退出提醒不应散落到别的产品面。"),
            ("策略实验", "回测、胜率、排名与内部策略接口都属于平台核心能力。"),
        ],
        "hero_aside_title": "策略平台原则",
        "hero_aside_items": [
            "平台端首先是策略驾驶舱，而不是普通资料管理页。",
            "买入预警、退出策略、实验验证和执行确认应尽量在同一工作台内闭环。",
            "即使部分高权限策略接口暂时挂在内部 API 下，产品归属也仍应视为平台核心。",
            "默认复用 app 会话，避免研究、决策和执行之间重复登录。",
        ],
        "body": _PLATFORM_BODY,
        "script": _PLATFORM_SCRIPT,
    },
    "admin": {
        "title": "管理端",
        "hero_title": "管理端聚焦用户、推送、治理和监控，策略本身不是这里的产品中心。",
        "hero_copy": "next/admin 被重新定义为运营治理面。管理员在这里处理用户生命周期、消息运营、权限审计和运行监控；scanner、backtests、analytics 等只作为内部高权限观测面存在，用来支撑平台治理。",
        "hero_stats": [
            ("用户与订阅", "用户资料、订阅状态、套餐调整和启停管理属于 admin 主责。"),
            ("推送与任务", "消息分发、发件箱、回执和人工复核任务属于运营链路。"),
            ("治理与监控", "权限、审计、运行态与发布证据共同构成管理端核心。"),
        ],
        "hero_aside_title": "运营后台原则",
        "hero_aside_items": [
            "先确认当前身份和权限上下文，再进行用户、消息或治理操作。",
            "把用户、推送、权限、审计和运行监控放在相邻工作域，降低值班遗漏。",
            "策略相关页只作为内部观测和应急入口，不把管理端继续写成策略驾驶舱。",
            "依然保留纯 HTML + Python 部署优势，便于在受限环境下快速接入。",
        ],
        "body": _ADMIN_BODY,
        "script": _ADMIN_SCRIPT,
    },
}


def _render_nav(surface: SurfaceName) -> str:
    return _render_nav_for_paths(surface, path_map=_build_surface_path_map())


def _build_surface_path_map(route_prefix: str | None = None) -> dict[SurfaceName, str]:
    normalized_prefix = str(route_prefix or "").strip().strip("/")
    base = f"/{normalized_prefix}" if normalized_prefix else ""
    return {
        "app": f"{base}/app",
        "platform": f"{base}/platform",
        "admin": f"{base}/admin",
    }


def _render_nav_for_paths(
    surface: SurfaceName,
    *,
    path_map: dict[SurfaceName, str],
    stable_path_map: dict[SurfaceName, str] | None = None,
    switcher_path: str | None = None,
) -> str:
    items = [
        ("app", path_map["app"], "订阅端"),
        ("platform", path_map["platform"], "平台端"),
        ("admin", path_map["admin"], "管理端"),
    ]
    chips: list[str] = []
    for item_surface, href, label in items:
        class_name = "nav-chip active" if item_surface == surface else "nav-chip"
        chips.append(f'<a class="{class_name}" href="{href}">{escape(label)}</a>')
    if stable_path_map is not None:
        chips.append(
            f'<a class="nav-chip" href="{stable_path_map[surface]}">切回稳定版</a>'
        )
    if switcher_path:
        chips.append(f'<a class="nav-chip" href="{switcher_path}">版本切换</a>')
    return "".join(chips)


def render_surface_page(
    *,
    surface: SurfaceName,
    project_name: str,
    public_api_base_url: str | None = None,
    admin_api_base_url: str | None = None,
    route_prefix: str | None = None,
    switcher_path: str | None = None,
    experimental: bool = False,
) -> str:
    meta = _PAGE_META[surface]
    path_map = _build_surface_path_map(route_prefix)
    stable_path_map = _build_surface_path_map() if experimental else None
    page_config = json.dumps(
        {
            "surface": surface,
            "projectName": project_name,
            "publicApiBaseUrl": public_api_base_url or "",
            "adminApiBaseUrl": admin_api_base_url or "",
        }
    )
    brand_copy = (
        "并行新版本，不影响当前页面；不满意可立即切回稳定版。"
        if experimental
        else "订阅端、桌面端与管理端的统一入口。"
    )
    hero_kicker = "股票订阅系统并行新版" if experimental else "股票订阅系统三端入口"

    html = _PAGE_TEMPLATE
    replacements = {
        "__TITLE__": escape(
            f"{project_name} {meta['title']}" + (" · 并行新版" if experimental else "")
        ),
        "__SURFACE__": escape(surface),
        "__BRAND__": escape(project_name),
        "__BRAND_COPY__": escape(brand_copy),
        "__NAV__": _render_nav_for_paths(
            surface,
            path_map=path_map,
            stable_path_map=stable_path_map,
            switcher_path=switcher_path,
        ),
        "__HERO_KICKER__": escape(hero_kicker),
        "__HERO_TITLE__": escape(meta["hero_title"]),
        "__HERO_COPY__": escape(meta["hero_copy"]),
        "__HERO_STATS__": _render_hero_stats(meta["hero_stats"]),
        "__HERO_ASIDE_TITLE__": escape(meta["hero_aside_title"]),
        "__HERO_ASIDE_ITEMS__": _render_hero_aside_items(meta["hero_aside_items"]),
        "__APP_PATH__": escape(path_map["app"]),
        "__PLATFORM_PATH__": escape(path_map["platform"]),
        "__ADMIN_PATH__": escape(path_map["admin"]),
        "__BODY__": meta["body"],
        "__PAGE_CONFIG__": page_config,
        "__COMMON_SCRIPT__": _COMMON_SCRIPT,
        "__PAGE_SCRIPT__": meta["script"],
    }
    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)
    return html