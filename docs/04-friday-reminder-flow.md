# 4. Weekly emails (Power Automate)

Two scheduled flows keep the logging habit going without nagging reps in weeks they aren't out selling:

| Flow | When | Who gets it | What it says |
|---|---|---|---|
| **A. Friday reminder** | Friday 3 pm | Each active rep who logged **nothing** in the app this week | "If you made calls this week, log those days, and update your MFP season-to-date units." |
| **B. Monday digest** | Monday 8 am | You (and later, the other manager) | Each rep's selling days logged last week, and who logged nothing |

Reps should update their MFP units at least weekly, even in weeks they don't sell. In the app that's **Log a Day** with 0 calls, 0 contacts and the units filled in. So "logged nothing this week" is a fair trigger for a reminder, even during quiet weeks.

**Build them as a manager.** The flows run with the builder's SharePoint connection, and only managers can see every rep's rows and the Reps list.
**License:** these use only the SharePoint and Office 365 Outlook connectors, which M365 Business and Enterprise plans include for standard use. Confirm against your own plan.

> **Honesty note:** the steps and expressions below are written carefully but haven't been run in your tenant. If a step shows an error, copy it and send it over.

---

## Flow A: "Friday log reminder"

**make.powerautomate.com → + Create → Scheduled cloud flow**

1. **Recurrence:** every **1 Week** on **Friday** at **3:00 PM**. Set **Time zone** to your local zone (Central, Eastern, …).

2. **Get items (SharePoint): "Get current season"**
   - Site: Sales Planner. List: **Seasons**
   - Filter Query: `CurrentSeason eq 1`
   - Top Count: `1`

3. **Condition: "Is a season running?"** Stop if there's no current season, or today falls outside it:
   - `length(body('Get_current_season')?['value'])` **is greater than** `0`
   - **AND** `formatDateTime(utcNow(),'yyyy-MM-dd')` **is greater than or equal to** `formatDateTime(first(body('Get_current_season')?['value'])?['SeasonStart'],'yyyy-MM-dd')`
   - **AND** `formatDateTime(utcNow(),'yyyy-MM-dd')` **is less than or equal to** `formatDateTime(addDays(first(body('Get_current_season')?['value'])?['SeasonStart'], mul(first(body('Get_current_season')?['value'])?['Weeks'], 7)),'yyyy-MM-dd')`

   Put everything below in the **If yes** branch.

4. **Get items: "Get active reps"**: List **Reps**, Filter Query `Active eq 1`

5. **Get items: "Get this week's activity"**: List **Daily Activity**, Filter Query:

   ```
   ActivityDate ge '@{formatDateTime(addDays(utcNow(), -6), 'yyyy-MM-dd')}'
   ```

   (Saturday through Friday.)

6. **Apply to each** over `body('Get_active_reps')?['value']`:

   a. **Filter array: "This rep's days"**
      - From: `body('Get_this_week''s_activity')?['value']` (pick it from Dynamic content so the name matches)
      - Advanced mode:

        ```
        @equals(toLower(item()?['Author']?['Email']), toLower(items('Apply_to_each')?['RepUser']?['Email']))
        ```

   b. **Condition:** `length(body('This_rep''s_days'))` **is equal to** `0`

   c. **If yes → Send an email (V2)** (Office 365 Outlook)
      - To: `items('Apply_to_each')?['RepUser']?['Email']`
      - Subject: `Quick reminder: log your week`
      - Body:

        > Hi @{items('Apply_to_each')?['Title']},
        >
        > Nothing's been logged in the **Rite Bite Sales Planner** app this week. If you made calls or contacts, log each selling day (about 20 seconds each). Either way, please update your **MFP season-to-date units**. Use **Log a Day** with 0 calls if you didn't sell this week.
        >
        > Thanks!

7. **Save**, then **Test → Manually**. For a test, tick *Current Season* on a season that includes today, or the condition in step 3 stops the flow.

## Flow B: "Monday activity digest" (to managers)

Copy Flow A (**… → Save As**) and change:

1. **Recurrence:** **Monday 8:00 AM**.
2. **Get this week's activity** → rename it **"Get last week's activity"**, Filter Query (last Monday through Sunday):

   ```
   ActivityDate ge '@{formatDateTime(addDays(utcNow(), -7), 'yyyy-MM-dd')}' and ActivityDate lt '@{formatDateTime(utcNow(), 'yyyy-MM-dd')}'
   ```

3. Before the loop, add **Initialize variable** `lines` (Array).
4. Inside the loop, replace the condition and email with one **Append to array variable** `lines`, value:

   ```
   @{items('Apply_to_each')?['Title']}: @{length(body('This_rep''s_days'))} day(s) logged
   ```

5. After the loop: **Send an email (V2)** to the managers:
   - Subject: `Sales Planner: last week's activity`
   - Body: `@{join(variables('lines'), '<br>')}` then a line pointing to the app's **Team** screen for calls and contacts against target.

## Notes

- **Column internal names** used in the filters (`CurrentSeason`, `SeasonStart`, `Weeks`, `Active`, `ActivityDate`, `RepUser`) are set by the setup script, so they're fixed regardless of the display names.
- If a rep leaves, untick **Active** in the Reps list and they stop getting emails.
- If the flow's owner leaves the company, the flow stops. Add the second manager as a **co-owner** of both flows.
- Want the Friday email to go to everyone, not just reps who logged nothing? Delete the condition in step 6b and put the email directly in the loop.
