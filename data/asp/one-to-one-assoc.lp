% A generic one-to-one association.

% The configuration is expected to have the following values:
%    {
%        "base encoding file": "data/asp/one-to-one-assoc.lp",
%        "shows": "assoc/2",
%        "choices options": {
%            "type": "multiple",
%            "data atoms": [
%                "user({user})",
%                "choice({choice})"
%            ],
%            "produced atoms": "ok({user},{choice})"
%        }
%    }


% each user is associated with one choice, that user marked ok.
1 { assoc(H, P): choice(P), ok(H,P) } 1 :- user(H).

% each choice is associated with one user, that user marked ok.
1 { assoc(H, P): user(H), ok(H,P) } 1 :- choice(P).
