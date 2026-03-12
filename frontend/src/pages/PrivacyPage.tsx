import { Container, Typography, Box, Divider } from '@mui/material';

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Box sx={{ mb: 3 }}>
      <Typography variant="h6" gutterBottom sx={{ mt: 3 }}>
        {title}
      </Typography>
      {children}
    </Box>
  );
}

function Subsection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Box sx={{ mb: 1.5 }}>
      <Typography variant="subtitle1" fontWeight={600} gutterBottom>
        {title}
      </Typography>
      {children}
    </Box>
  );
}

function Bullets({ items }: { items: React.ReactNode[] }) {
  return (
    <Box component="ul" sx={{ mt: 0.5, pl: 3 }}>
      {items.map((item, i) => (
        <Typography component="li" variant="body2" key={i} sx={{ mb: 0.5 }}>
          {item}
        </Typography>
      ))}
    </Box>
  );
}

export default function PrivacyPage() {
  return (
    <Container maxWidth="md" sx={{ mt: 3, mb: 6 }}>
      <Typography variant="h4" gutterBottom>
        Privacy Policy
      </Typography>
      <Typography variant="body2" color="text.secondary" gutterBottom>
        Last updated: March 2026
      </Typography>
      <Typography variant="body1" sx={{ mt: 1 }}>
        Bear Tracks (tracker.ancientbearrepublic.com) is a community tool for recording and
        analyzing KeyForge matches. This policy explains what data we collect, how it is used,
        what is made public, and what is kept private.
      </Typography>

      <Divider sx={{ my: 3 }} />

      <Section title="The short version">
        <Bullets
          items={[
            'Game data you upload — or that is uploaded on your behalf — is made publicly visible. That is the core purpose of this site.',
            'We will never sell your data in bulk to third parties. Some advanced analytics may be limited to paid supporters.',
            'Technical data like IP addresses and email addresses is kept private and is not redistributed.',
          ]}
        />
      </Section>

      <Section title="What data we collect">
        <Subsection title="Game and match data">
          <Typography variant="body2" sx={{ mb: 1 }} color="text.secondary">
            The following lists are representative, not exhaustive. As new features are added,
            additional game-related data may be collected and made public under the same principles.
          </Typography>
          <Bullets
            items={[
              <>
                <strong>Intended to be public:</strong> Crucible usernames, deck names, deck IDs
                (Master Vault UUIDs), game outcomes (winner, keys forged), date and time of play,
                house choices, key forge events (turn number, amber paid, key color), per-turn
                timing, and board state snapshots captured at each house selection.
              </>,
              <>
                <strong>League data:</strong> Team names, league standings, weekly matchup
                results, deck selections for league weeks, and sealed/alliance pod selections are
                stored and displayed publicly as part of league management features.
              </>,
            ]}
          />
        </Subsection>

        <Subsection title="Account data">
          <Bullets
            items={[
              <>
                <strong>Email address:</strong> Used for account login and password recovery. If
                you participate in a league, your email address will be visible to league
                administrators and team captains for coordination purposes. It is not displayed
                publicly.
              </>,
              <>
                <strong>Time zone:</strong> If you set a time zone in your profile, it will be
                shared with league administrators, team captains, and your opponents within a
                league to help schedule matches. It is not displayed on your public profile.
              </>,
              <>
                <strong>Discord username:</strong> If you link a Discord account, your Discord
                username will be displayed publicly on your player profile and shared within
                leagues to help players coordinate.
              </>,
              <>
                <strong>Future profile fields:</strong> If additional contact or scheduling fields
                (such as physical address for in-person events) are added to player profiles, they
                will follow the same pattern: shared with league administrators and team captains
                as needed for league operations, with any public/private distinction noted clearly
                in the interface when you provide the information.
              </>,
              <>
                <strong>Patreon connection:</strong> If you connect a Patreon account to unlock
                premium features, we receive your Patreon username and membership tier from
                Patreon's OAuth service. We do not store your Patreon payment details.
              </>,
            ]}
          />
        </Subsection>

        <Subsection title="Collection data">
          <Bullets
            items={[
              'If you sync your deck collection (via Master Vault or manual upload), your collection contents may be stored and may be surfaced publicly in deck search or player profile views.',
            ]}
          />
        </Subsection>

        <Subsection title="Technical data">
          <Bullets
            items={[
              <>
                <strong>IP addresses and server logs:</strong> Collected automatically as part of
                normal web server operation. Used only for security and debugging. Not
                redistributed.
              </>,
              <>
                <strong>Cookies and session tokens:</strong> We use session cookies to keep you
                logged in. These are standard authentication cookies and are not used by us for
                advertising or cross-site tracking. Third-party integrations (such as Google
                reCAPTCHA and Discord OAuth) may set their own cookies; those are governed by
                their respective privacy policies.
              </>,
            ]}
          />
        </Subsection>
      </Section>

      <Section title="How game data is made public">
        <Bullets
          items={[
            'Every game uploaded to Bear Tracks is publicly visible at both the individual game level (full log, deck names, result) and the aggregate level (player win rates, deck statistics, timing analytics, key forge averages). There is no option to upload a game privately.',
            'We may periodically publish bulk data dumps containing game and deck statistics. Once a bulk dump has been published, we cannot retroactively remove data from copies others may have downloaded.',
            'By uploading a game — or by using the KeyTracker browser extension which uploads automatically — you are accepting that the game data will be made public.',
          ]}
        />
      </Section>

      <Section title="The KeyTracker browser extension">
        <Bullets
          items={[
            'The KeyTracker Chrome extension captures game events directly from The Crucible (thecrucible.online) while you play. This includes the game log, deck information, turn timing, house choices, key forge events, and snapshots of board state at each turn.',
            'Captured data is submitted to tracker.ancientbearrepublic.com. The extension does not transmit data to any other destination.',
            'Auto-submit is enabled by default. You can disable it in the extension settings and submit games manually instead.',
            'The extension stores session data locally in your browser (chrome.storage.local) temporarily during play. This local data is cleared once the session is submitted or manually cleared.',
          ]}
        />
      </Section>

      <Section title="Premium analytics (Patreon)">
        <Bullets
          items={[
            'Some advanced analytical features may be restricted to paid supporters via Patreon. The underlying game data itself is always public; only certain analysis tools may be gated.',
            'We do not sell data to generate revenue. Patreon support funds server costs and development.',
          ]}
        />
      </Section>

      <Section title="Data we will not share or sell">
        <Bullets
          items={[
            'Email addresses (except with league admins/captains as described above)',
            'IP addresses and server log details',
            'Patreon payment information',
            'Any personal identifying information that is not relevant to the game',
          ]}
        />
        <Typography variant="body2" sx={{ mt: 1 }}>
          We will not sell user data in bulk to third parties for advertising, research, or any
          other commercial purpose.
        </Typography>
      </Section>

      <Section title="Data modification and deletion">
        <Bullets
          items={[
            'Bear Tracks may modify or remove data at administrators\' discretion, including in response to user requests, to correct inaccuracies, or to remove data that was acquired illegally or inappropriately.',
            'If you would like your account deleted, contact us. Account deletion will remove your login credentials and profile, but game records you participated in will remain (with your username intact unless you also request anonymization — see below).',
          ]}
        />
      </Section>

      <Section title="Your Crucible username: anonymization requests">
        <Bullets
          items={[
            'If you do not want your Crucible username to appear in Bear Tracks\' database, you may request that all occurrences be replaced with "anonymous."',
            'To make this request, contact the administrators. You will need to provide reasonable evidence that you control the Crucible account in question.',
            'Upon approval, administrators will anonymize all existing records containing your username and add it to the exclusion list so future uploads are anonymized automatically.',
            <>
              <strong>This is a one-way change.</strong> We cannot restore anonymized data if you
              change your mind later, and we cannot affect bulk data dumps that were published
              before your request was processed.
            </>,
          ]}
        />
      </Section>

      <Section title="Responsibility for uploaded data">
        <Bullets
          items={[
            'The person uploading game data is responsible for having obtained it through appropriate and legal means.',
            'If we become aware that data was acquired illegally or in violation of The Crucible\'s terms of service, we will remove it.',
          ]}
        />
      </Section>

      <Section title="Changes to this policy">
        <Typography variant="body2">
          We may update this policy as features are added. Material changes will be noted with a
          new "Last updated" date at the top. Continued use of the site after a policy update
          constitutes acceptance of the revised policy.
        </Typography>
      </Section>

      <Section title="Contact">
        <Typography variant="body2">
          Questions or requests (anonymization, account deletion, data concerns) can be directed
          to the administrators via the{' '}
          <a href="https://ancientbearrepublic.com" target="_blank" rel="noreferrer">
            Ancient Bear Republic
          </a>{' '}
          community channels or by filing an issue on the project's GitHub repository.
        </Typography>
      </Section>
    </Container>
  );
}
