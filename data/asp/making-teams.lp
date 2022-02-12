% A generic team creation, trying to maximize wanted associations of users/players.

#const nb_teams=2.

% each user/player is in a team.
1 { team(U,1..nb_teams) } 1 :- user(U).
% at least one user/player in each team
1 { team(U,T): user(U) } :- T=1..nb_teams.

% Ensure each team has the same number of users.
%  (or only one more/less, to handle cases like 2 teams,
%   but odd number of users)
teamsize(T,S) :- team(_,T) ; S={team(_,T)}.
:- teamsize(T1,S1) ; teamsize(T2,S2) ; |S1-S2|>1.

% Compute and maximize the score.
%  Score is 1 for each other user i want in my team that is in my team.
score(S) :- S=#sum{1,H,C: ok(H,C), team(H,T), team(C,T)}.
#maximize{S@1:score(S)}.

