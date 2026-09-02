# Let Claude read your Messages

This lets you ask Claude questions about your text messages, like
"who haven't I heard from in a while?" or "when did I last talk to Sarah?"

Everything stays on your Mac. Your messages are never uploaded anywhere.
Claude can only read them — it cannot send, change, or delete anything.

Setting this up takes about five minutes.

---

## Before you start

Make sure the **Claude** app is installed on your Mac and you have signed in.
If not, get it from **claude.ai/download** first.

---

## Step 1 — Put the folder somewhere safe

Move the `imessage-mcp` folder to your **Documents** folder.

Once it is set up, leave it there. If you move or delete this folder later,
it will stop working.

---

## Step 2 — Run the installer

Inside the folder, find the file called **Install**.

**Right-click it** (or hold Control and click), then choose **Open**.

> **Important:** right-click and choose Open. Do not just double-click it the
> first time. Your Mac blocks downloaded files unless you open them this way.

A warning may appear saying the file is from an unidentified developer.
Click **Open** to continue.

A black window will open and print what it is doing. This takes a minute or two.
When it says it is almost done, move on to Step 3.

---

## Step 3 — Give Claude permission (you must do this part yourself)

Your Mac keeps messages private, so it will not let any app read them until
you personally say yes. Nobody can do this step for you.

1. Open **System Settings** (the grey gear icon)
2. Click **Privacy & Security** in the left sidebar
3. Scroll down and click **Full Disk Access**
4. Find **Claude** in the list and turn the switch **on**
   - If Claude is not in the list, click the **+** button, then pick
     **Claude** from your Applications folder
5. Enter your Mac password if it asks

---

## Step 4 — Restart Claude completely

This step is the one people miss, and nothing works without it.

1. Click on Claude
2. Press **Command-Q** (hold ⌘ and tap Q) to quit it fully
3. Open Claude again

Closing the window is **not** enough. Your Mac only checks the new permission
when the app starts fresh.

---

## Step 5 — Try it

Open Claude and start a normal chat, the same way you always do.
There is no special mode or button to press.

Type:

> who have I not texted in over a month?

The first time you ask, Claude may show a small box asking permission to use
the messages tool. Click **Allow**.

If it answers with real names from your phone, you are done.

---

## If something goes wrong

**"Cannot read the iMessage database"**
Permission is missing or Claude was not fully restarted.
Go back to Step 3 and Step 4. The Command-Q restart is usually the problem.

**You see phone numbers instead of names**
Claude could not read your Contacts. Everything else still works.
Turning on Full Disk Access in Step 3 usually fixes this too.

**Claude says it cannot see your messages, or acts confused by the question**
The installer may not have finished. Run Step 2 again and read the last few
lines in the black window. If it says it could not find the Claude app, make
sure Claude is in your Applications folder, then run it once more.

Also double-check Step 4. Quitting with Command-Q and reopening is required
after the installer runs, not just after changing the permission.

**You want to turn it off**
Go to System Settings > Privacy & Security > Full Disk Access and switch
Claude off. It will immediately lose access to your messages.
