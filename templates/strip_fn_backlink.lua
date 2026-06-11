-- Pandoc EPUB-only lua filter.
--
-- Merges multi-paragraph footnotes into a single block so reader popovers
-- render the note's body as continuous text rather than truncating after
-- the first paragraph (a CLAUDE.md "open work" parked issue, mostly LS).
--
-- The pandoc EPUB writer adds the leading back-link itself after this
-- filter runs, so the cosmetic "N. " redundancy in Apple Books popovers
-- is neutralised in CSS (templates/epub.css), not here.

function Note (el)
  if #el.content < 2 then
    return el
  end

  local merged = pandoc.List()
  for _, blk in ipairs(el.content) do
    if blk.t == "Para" or blk.t == "Plain" then
      if #merged > 0 then
        -- Two LineBreaks survive reader stripping of leading whitespace
        -- and read as a real paragraph break inside the popover.
        merged:insert(pandoc.LineBreak())
        merged:insert(pandoc.LineBreak())
      end
      merged:extend(blk.content)
    end
  end

  el.content = { pandoc.Para(merged) }
  return el
end

function Pandoc (doc)
  -- Pandoc injects the metadata title as an empty-body H1 for EPUB, then
  -- nests every real structural heading beneath it in the navigation tree.
  -- The title already belongs to EPUB metadata and the title-page landmark;
  -- remove only that synthetic heading, leaving genuine H1 parts untouched.
  --
  -- Matching is by text: a *real* leading H1 whose text equals the document
  -- title would be eaten too. That cannot arise from make_book.py, which
  -- only emits H1s for part headings ("Part N: …" / part titles), never the
  -- document name — revisit this check if that ever changes.
  local title = pandoc.utils.stringify(doc.meta.title or '')
  if title ~= '' and doc.blocks[1]
      and doc.blocks[1].t == 'Header'
      and doc.blocks[1].level == 1
      and pandoc.utils.stringify(doc.blocks[1].content) == title then
    doc.blocks:remove(1)
  end
  return doc
end
