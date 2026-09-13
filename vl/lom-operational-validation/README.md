# LOM P6.7 Operational Validation

Status: DEVELOPMENT / NON-PRODUCTION

This module validates continuity across the integrated LOM P6 opportunity pipeline using repository evidence.

Validation goals:
- detect active live signals that disappear before conversion
- preserve HOLD and WATCHLIST semantics across stages
- detect conflicting active dates or states when the same normalized opportunity is present in both stages
- keep historical/watchlist records from being treated as active pursuits
- fail closed when required upstream evidence is absent

Known real-world validation finding at inception: the live register contains the active Pagalungan water-pipe signal, while the conversion queue does not contain a corresponding conversion item. The validator must surface this as a continuity gap rather than silently treating the loop as complete.

Operational validation does not promote opportunities, contact customers, submit bids or quotations, change pricing, mutate production, change authority, or merge protected main.
