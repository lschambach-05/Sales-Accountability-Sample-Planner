# 4. Friday reminder flow (Power Automate)

This is where the accountability comes from. Every Friday afternoon, any active rep who hasn't submitted that week's check-in gets an email. On Monday morning, the two managers get a short list of who still hasn't.

**Build it as a manager.** The flow runs with the builder's SharePoint connection, and only managers can see every rep's check-ins and the Reps list.
**License:** uses only the SharePoint and Office 365 Outlook connectors, which M365 Business and Enterprise plans include for standard use. Confirm against your own plan.

---

## Flow A: "Friday check-in reminder"

**make.powerautomate.com → + Create → Scheduled cloud flow**

1. **Recurrence:** every **1 Week** on **Friday** at **3:00 PM**. Set **Time zone** to your local zone (Central, Eastern, …).

2. **Get items (SharePoint): "Get current season"**
   - Site: Sales Planner. List: **Seasons**
   - Filter Query: `CurrentSeason eq 1`
   - Top Count: `1`

3. **Condition: "Is a season running?"** Stop if there's no current season, or if today falls outside it:
   - `length(body('Get_current_season')?['value'])` **is greater than** `0`
   - **AND** `formatDateTime(utcNow(),'yyyy-MM-dd')` **is greater than or equal to** `formatDateTime(first(body('Get_current_season')?['value'])?['SeasonStart'],'yyyy-MM-dd')`
   - **AND** `formatDateTime(utcNow(),'yyyy-MM-dd')` **is less than or equal to** `formatDateTime(addDays(first(body('Get_current_season')?['value'])?['SeasonStart'], mul(first(body('Get_current_season')?['value'])?['Weeks'], 7)),'yyyy-MM-dd')`

   Put everything below in the **If yes** branch.

4. **Get items: "Get active reps"**: List **Reps**, Filter Query `Active eq 1`

5. **Get items: "Get this week's check-ins"**: List **Weekly Check-ins**, Filter Query:

   ```
   WeekEnding ge '@{formatDateTime(addDays(utcNow(), -2), 'yyyy-MM-dd')}' and WeekEnding le '@{formatDateTime(addDays(utcNow(), 2), 'yyyy-MM-dd')}'
   ```

   (This is a ±2-day window so time zones can't make Friday's row slip to Thursday or Saturday.)

6. **Apply to each** over `body('Get_active_reps')?['value']`:

   a. **Filter array: "This rep's check-in"**
      - From: `body('Get_this_week''s_check-ins')?['value']` (pick it from Dynamic content so the name matches)
      - Advanced mode:

        ```
        @equals(toLower(item()?['Author']?['Email']), toLower(items('Apply_to_each')?['RepUser']?['Email']))
        ```

   b. **Condition:** `length(body('This_rep''s_check-in'))` **is equal to** `0`

   c. **If yes → Send an email (V2)** (Office 365 Outlook)
      - To: `items('Apply_to_each')?['RepUser']?['Email']`
      - Subject: `Friday check-in reminder`
      - Body:

        > Hi @{items('Apply_to_each')?['Title']},
        >
        > Your weekly sales check-in for the week ending @{formatDateTime(utcNow(),'MMMM d')} isn't in yet. It takes about a minute in the **Rite Bite Sales Planner** app: calls, indirect contacts, sales days, and your MFP season-to-date units.
        >
        > Thanks!

7. **Save** and use **Test → Manually** to try it. If the test runs outside a season, the condition in step 3 stops it, so for a test tick *Current Season* on a season that includes today.

## Flow B: "Monday missing check-ins" (to managers)

Copy Flow A (**… → Save As**) and change:

1. **Recurrence:** **Monday 8:00 AM**.
2. **Get this week's check-ins** window: last Friday ± 2 days:

   ```
   WeekEnding ge '@{formatDateTime(addDays(utcNow(), -5), 'yyyy-MM-dd')}' and WeekEnding le '@{formatDateTime(addDays(utcNow(), -1), 'yyyy-MM-dd')}'
   ```

3. Before the loop, add **Initialize variable** `missing` (Array).
4. Inside the loop, in **If yes**, replace the email with **Append to array variable** `missing` → `items('Apply_to_each')?['Title']`.
5. After the loop: **Condition** `length(variables('missing'))` **greater than** `0` → **Send an email (V2)** to both managers:
   - Subject: `Check-ins missing for last week`
   - Body: `Still missing: @{join(variables('missing'), ', ')}`

## Notes

- **Column internal names** used in the filters (`CurrentSeason`, `SeasonStart`, `Weeks`, `Active`, `WeekEnding`, `RepUser`) are set by the setup script, so they're fixed regardless of the display names.
- If a rep leaves, untick **Active** in the Reps list and they stop getting emails.
- If the flow's owner leaves the company, the flow stops. Add the second manager as a **co-owner** of both flows.
