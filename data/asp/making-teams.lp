% A generic team creation, trying to maximize wanted associations of users/players.

#const nb_teams=2.

% each user/player is in a team.
1 { team(1..nb_teams,U) } 1 :- user(U).
% at least one user/player in each team
1 { team(T,U): user(U) } :- T=1..nb_teams.

% Ensure each team has the same number of users.
%  (or only one more/less, to handle cases like 2 teams,
%   but odd number of users)
teamsize(T,S) :- team(T,_) ; S={team(T,_)}.
:- teamsize(T1,S1) ; teamsize(T2,S2) ; |S1-S2|>1.

% Compute and maximize the score.
%  Score is 1 for each other user i want in my team that is in my team.
score(S) :- S=#sum{1,H,C: ok(H,C), team(T,H), team(T,C)}.
#maximize{S@1:score(S)}.

