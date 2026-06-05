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
