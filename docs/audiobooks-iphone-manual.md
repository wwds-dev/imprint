# Imprint audiobooks on Mac and iPhone

**Status: 29 September 2026.** Imprint can save converted audio and listening
progress either locally or in your synced `My Drive/audiobooks - gdrive` folder.
The Imprint audiobook web agent has been implemented in source, but it is
**not yet connected or deployed**. A dedicated Google Cloud project
(`imprint-audiobooks`) now exists, but it has no active Cloud Billing account.
The iPhone conversion and shared playback steps below become available only
after the cloud service, Google OAuth connection, and updated Netlify dashboard
are deployed and tested. Until then, use the Mac workflow in the next section.

## Convert on the Mac now

1. Open a rebuilt Imprint app and go to **Narrator → Convert**.
2. Add a DRM-free EPUB, PDF, TXT, or MOBI ebook to the Narrator input folder.
   MOBI needs Calibre's `ebook-convert` command. Select the book after **Refresh
   List**.
3. Under **Save converted audio**, choose **On this Mac** or **Google Drive
   folder**. For Drive, set the output folder to your synced
   `My Drive/audiobooks - gdrive` folder.
4. Choose **Convert audiobook**, review Imprint's estimate, and confirm the
   OpenAI text-to-speech charge. Keep the Mac running until it completes.

The finished MP3 is in a subfolder named after the book. If you saved to Drive,
allow Drive for desktop to finish syncing before opening it on the phone.

## Choose where Imprint saves playback progress

1. Open **Narrator → Listen** in Imprint.
2. Under **Save listening progress**, choose **On this Mac** for progress only
   on the computer, or **Google Drive folder** to share progress with the
   Imprint web player. Choose the same
   `My Drive/audiobooks - gdrive` folder.
3. Imprint copies progress and saved marks for books it finds in the output
   folder when you switch modes. It leaves existing destination records intact.
4. In Drive mode, progress is stored in `Imprint Progress` inside the selected
   Drive folder. Imprint saves during playback and when you pause or stop.

If Imprint cannot see the Drive folder, it shows a save error. The phone player
cannot sync with Imprint when **On this Mac** is selected.

## Use the iPhone after cloud setup is complete

1. In Safari, open the private
   [Reading Compass dashboard](https://reading-compass-private.netlify.app/)
   and sign in to its Netlify access page.
2. Open **Narrator → Open Imprint web agent**. Choose **Connect Google Drive**
   and sign in with the Google account that owns `My Drive/ebooks` and
   `My Drive/audiobooks - gdrive`. Approve the requested Drive access.
3. On **Convert**, search for an EPUB, PDF, TXT, or MOBI book from
   `My Drive/ebooks`. You can also select **Queue audio** on a Reading Compass
   recommendation before opening the web agent; it will open with that book
   selected.
4. Choose a voice and chunk size, then tap **Estimate cost**. Read the
   estimated length and OpenAI charge before tapping **Convert audiobook**.
   Confirm the charge. The conversion runs in the cloud; your Mac can be off.
5. Check **Conversions** for queued, running, finished, or failed status.
   The finished MP3 appears on **Listen** and in
   `My Drive/audiobooks - gdrive/[book name]`.
6. On **Listen**, search for the book and tap it, then press **Play**. The web
   player offers 30-second skips, speed, sleep timer, saved marks, and an MP3
   download. Pause before switching devices. It saves the position during
   playback and on pause.
7. To continue in Imprint on the Mac, let Drive for desktop sync, open the same
   MP3 in **Narrator → Listen**, and use **Google Drive folder** for progress.
   Imprint resumes from the shared position. The reverse direction works too:
   pause in Imprint, wait for Drive sync, then reopen the book in Safari.

Use the Imprint web player's Listen page for synced position. The Google Drive app's MP3
preview and other audio players do not write Imprint's progress record. Drive
can still be used to find or download the MP3 itself.

## Connection requirements

- The Imprint audiobook web agent needs a billed Google Cloud project,
  Drive API access, Firestore, a Cloud Run service, a Cloud Run Job, an OAuth web
  client, and an OpenAI API key. The cloud service uses Imprint's own Narrator
  converter. Setup details are in `cloud/README.md` in the Imprint source.
- The dashboard currently stores reading statuses and preferences separately
  in each browser. Audiobook position sync uses Drive after cloud setup.
- A long book may incur substantial OpenAI and cloud charges. Start with a
  short ebook when testing the connection.
