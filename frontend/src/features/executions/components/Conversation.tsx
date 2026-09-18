import { Bot, ShieldCheck, User, Wrench } from 'lucide-react';
import { EmptyState } from '@/components/feedback/EmptyState';
import { Badge } from '@/components/ui/Badge';
import type { ConversationTurn } from '@/types/domain';

/**
 * What was said in a model-driven run, in order.
 *
 * Everything here is untrusted text - the requester's task, the model's words,
 * the arguments it chose - so it is rendered as plain text only. Nothing is
 * interpreted as markup, and no link or command in it is made actionable.
 */
export function Conversation({ turns }: { turns: ConversationTurn[] }) {
  if (turns.length === 0) {
    return (
      <EmptyState
        icon={Bot}
        title="No conversation"
        description="No model was called for this run, so there is nothing it said to show."
        className="py-8"
      />
    );
  }

  return (
    <ol className="space-y-4" aria-label="Conversation">
      {turns.map((turn, index) => (
        <li key={index} className="rounded-md border border-border px-4 py-3">
          <TurnHeader turn={turn} />
          {turn.text && (
            <p className="mt-2 text-sm break-words whitespace-pre-wrap text-fg">{turn.text}</p>
          )}
          {turn.toolCalls.length > 0 && (
            <ul className="mt-2 space-y-1.5" aria-label="Tools requested">
              {turn.toolCalls.map((call) => (
                <li key={call.id} className="flex flex-wrap items-baseline gap-2 text-xs">
                  <Wrench aria-hidden="true" className="size-3.5 shrink-0 self-center text-fg-subtle" />
                  <span className="font-mono font-medium text-fg">{call.name}</span>
                  <code className="min-w-0 font-mono break-all text-fg-muted">{call.arguments}</code>
                </li>
              ))}
            </ul>
          )}
          {turn.toolResults.length > 0 && (
            <ul className="mt-2 space-y-1.5" aria-label="Told the model">
              {turn.toolResults.map((result) => (
                <li key={result.callId} className="text-xs text-fg-muted">
                  {result.isError && (
                    <Badge tone="neutral" className="mr-2">
                      Not done
                    </Badge>
                  )}
                  <span className="break-words">{result.content}</span>
                </li>
              ))}
            </ul>
          )}
        </li>
      ))}
    </ol>
  );
}

function TurnHeader({ turn }: { turn: ConversationTurn }) {
  if (turn.role === 'assistant') {
    return (
      <p className="flex items-center gap-2 text-xs font-medium text-fg-muted">
        <Bot aria-hidden="true" className="size-4" /> Model
      </p>
    );
  }
  if (turn.toolResults.length > 0) {
    return (
      <p className="flex items-center gap-2 text-xs font-medium text-fg-muted">
        <ShieldCheck aria-hidden="true" className="size-4" /> Tool gateway
      </p>
    );
  }
  return (
    <p className="flex items-center gap-2 text-xs font-medium text-fg-muted">
      <User aria-hidden="true" className="size-4" /> Request
    </p>
  );
}
