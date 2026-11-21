# Example widgets

Two copyable briefing widgets, here to be copied, not run. This
folder is not one of the renderer's scan roots (`briefing/widgets/`
and a `widgets/` folder inside or beside the data directory are), so
nothing in here ever appears in a briefing, and editing these files
in place changes nothing on the panel. That is deliberate: examples
stay stable while households experiment on their own copies.

To use one:

1. Copy the widget's folder into the `widgets/` folder of your data
   directory (the folder you pass with `--data`), or into
   `briefing/widgets/` to share it with every briefing this repo
   renders.
2. Edit `data.json` so it says something true, and `widget.json` if
   you want a different title, slot, or order.
3. Render as usual and look at the result:

```bash
python3 briefing/render_briefing.py --data /path/to/exports \
    --profile panel --out briefing.html
```

`weekend-chores` is an `items` widget and declares a `max_items`
setting, so it also shows how settings work: put
`{"weekend-chores": {"max_items": "3"}}` in `settings.json` in the
data directory and only three chores print. `house-plants` is a
`status` widget. The full contract is in [../WIDGETS.md](../WIDGETS.md).
