# Site Builder

> **Outcome:** build, save and browser-test one responsive page against a
> written client or business acceptance checklist.

![Site Builder workspace](../img/agent-webdesign.png)

## Prerequisites

- One page goal, audience, CTA, required content, brand constraints, and output
  boundary.
- Authoritative copy/data and rights for media/fonts.
- A plan for hosting, forms, analytics, privacy, and security outside generation.

## Control atlas

| Control/tab | Meaning |
|---|---|
| Brief/provider/model | Generates a proposed implementation; recommendations optimise the task route |
| HTML / CSS / JS | Separate editable outputs that must work together |
| Copy All | Copies the current complete proposal for review/use |
| Save .html | Writes a local deliverable; verify embedded/linked CSS and JS behavior |
| Clear | Clears visible output after saving; not undo |
| Stop | Requests local streaming cancellation |

## Recipe: build a one-page website

You will build and test a one-page website for a small local business — the
example is a dog groomer called *Paws & Suds*. Copy the example inputs exactly
the first time, then use a real business. Each **▶ Show me** closes this
lesson, opens the control it names and rings it; **Back to lesson** in the
callout brings you back to that step.

**Time:** about 25 minutes. **Cost:** one text request — you see its estimate
and approve it before anything is sent (free with a local Ollama model).
Hosting and a domain are separate and not part of this recipe.

### Step 1 — Choose the kind of page

Set **Page type** to `Landing Page`, **Style** to `Minimal` and **Framework**
to `Vanilla`. Vanilla means plain HTML, CSS and JavaScript in one file: nothing
to install, and it opens straight in a browser.

[Show me](show:webdesign_type_box)

### Step 2 — Give it colours

Give two or three colours as hex codes, then a few words for the feel.

```
#0f766e, #f8fafc, #f59e0b · calm teal with a warm amber accent
```

[Show me](show:webdesign_palette_input)

### Step 3 — Write the brief

List the sections in the order a visitor reads them, the one action you want
them to take, and what the page must *not* contain. Put `[PRICE]` and
`[PHONE]` where real details go, so none can be invented.

```
One-page site for Paws & Suds, a dog groomer in a small town.
Sections, in order:
1. Hero: name, one-line promise ("Clean, calm, happy dogs"), button
   "Book a groom" that calls [PHONE].
2. Services: Bath & brush, Full groom, Nail trim — each with [PRICE].
3. About: two sentences, friendly, family-run.
4. Opening hours and address: [HOURS], [ADDRESS].
5. Footer: phone, email [EMAIL], small print "© Paws & Suds".
Must: work on phones first, readable at 200% zoom, every button reachable
with the Tab key, visible focus outline, alt text on any image.
Must not: testimonials, star ratings, awards, invented prices, tracking
scripts, cookie banners, external fonts.
```

[Show me](show:webdesign_brief_input)

### Step 4 — Choose who writes the code

Pick a provider and model. **BEST FIT** marks the recommended choice for this
task. Larger models write cleaner, more complete pages; a local Ollama model
is free but may need a second try.

[Show me](show:webdesign_provider_box)

### Step 5 — Generate

Click **Generate** and approve the estimate. Code streams into the HTML tab.
When it finishes, the three numbers above the tabs fill in:
**responsive** (did it add mobile rules), **framework used** and **lines of
code**. For this brief expect *responsive: yes* and a few hundred lines.

[Show me](show:webdesign_generate_btn)

### Step 6 — Read what it made

Look through **HTML**, **CSS** and **JS**. You do not need to read code
fluently — check that every section from your brief is there, in order, and
that `[PRICE]`, `[PHONE]` and the other placeholders are still placeholders
rather than made-up values. A missing section means the brief needs to be
clearer; add it and generate again.

[Show me](show:webdesign_tabs)

### Step 7 — Save it as a file

Click **Save .html** and save it somewhere you will find it, such as your
Desktop. The file holds the whole page.

[Show me](show:webdesign_save_btn)

### Step 8 — Test it in a real browser

Double-click the saved file to open it in your browser, then:

1. Make the window as narrow as a phone. Nothing should be cut off or need
   sideways scrolling.
2. Press **Tab** repeatedly. You should always see where you are, and reach
   the *Book a groom* button.
3. Zoom to 200% (**⌘ +**). Text should reflow, not overlap.

If something fails, say exactly what in the brief (“the menu overlaps the
title below 400 px wide”) and generate again — the output tabs are read-only,
so the brief is where fixes go.

### Step 9 — Fill in the real details

Open the saved file in a text editor — or click **Copy All** and paste the
page into one — and replace every `[PLACEHOLDER]` with
the business's real details. The page is ready for hosting once the
acceptance checklist below passes.

[Show me](show:webdesign_copy_btn)

## How to read the output

Valid-looking code is a draft. A local page does not prove deployment,
analytics, form delivery, consent compliance, search indexing, security, or
conversion. Generated explanations are not test results.

## Acceptance checklist

- [ ] Content hierarchy and CTA match the brief.
- [ ] Keyboard, focus, labels, contrast, alt text, and zoom are usable.
- [ ] No overflow at target widths; touch targets and reduced motion are handled.
- [ ] Links/forms have real destinations and safe validation/error behavior.
- [ ] No secrets, fabricated proof, or unapproved tracking is embedded.
- [ ] The saved file works independently from the Imprint editor.

## Cost, cancellation, and gates

Text generation is only part of fulfilment cost; include design/review, assets,
hosting, testing, fixes, client revisions, and support. Humans approve claims,
data collection, credentials, deployment, domain changes, and client delivery.

## Verification

Open the saved file in a real browser and complete the acceptance checklist at
mobile and desktop widths using mouse, keyboard, and zoom.

## Common failures

**Page looks good but actions fail:** test integrated files, forms, and network
failure states.  
**Mobile clips:** add explicit responsive constraints and test the saved file.  
**The model invented content:** replace it with authoritative copy/data before
delivery.

## Done when

The saved page passes the written checklist in a real browser and the remaining
deployment/instrumentation work is explicit.

## Next action

For a client offer, continue to [Client Gigs](27-client-gigs.md); for demand
testing, define the funnel in [Design a fair experiment](32-experiment.md).
