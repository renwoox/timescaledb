# reorder should only be blocked by select for the final table swap
setup {
 CREATE TABLE ts_reorder_test(time int, temp float, location int);
 SELECT create_hypertable('ts_reorder_test', 'time', chunk_time_interval => 10);
 INSERT INTO ts_reorder_test VALUES (1, 23.4, 1),
       (11, 21.3, 2),
       (21, 19.5, 3);

 CREATE TABLE waiter(i INTEGER);
 -- like reluster_chunk execpt that it'll attempt to grab an release a ACCESS EXCLUSIVE
 -- lock on wait_on before swapping the tables. This allows us to control interleaving more.
 CREATE OR REPLACE FUNCTION reorder_chunk_i(
     chunk REGCLASS,
     index REGCLASS=NULL,
     verbose BOOLEAN=FALSE,
     wait_on REGCLASS=NULL
 ) RETURNS VOID AS '$libdir/timescaledb-1.2.0-dev', 'ts_reorder_chunk' LANGUAGE C VOLATILE;
}

teardown {
      DROP TABLE ts_reorder_test;
      DROP TABLE waiter;
}

session "S"
setup		{ BEGIN; SET LOCAL lock_timeout = '50ms'; SET LOCAL deadlock_timeout = '10ms';}
step "S1"	{ SELECT * FROM ts_reorder_test; }
step "Sc"	{ COMMIT; }

session "R"
setup		{ BEGIN; SET LOCAL lock_timeout = '50ms'; SET LOCAL deadlock_timeout = '10ms'; }
step "R1"	{ SELECT reorder_chunk_i((SELECT show_chunks('ts_reorder_test') LIMIT 1), 'ts_reorder_test_time_idx', wait_on => 'waiter'); }
step "Rc"	{ COMMIT; }

session "B"
setup		{ BEGIN; LOCK TABLE waiter; }
step "Bc"   { COMMIT; }

permutation "Bc" "S1" "Sc" "R1" "Rc"
permutation "Bc" "S1" "R1" "Sc" "Rc"
permutation "Bc" "S1" "R1" "Rc" "Sc"

permutation "Bc" "R1" "Rc" "S1" "Sc"
permutation "Bc" "R1" "S1" "Rc" "Sc"
permutation "Bc" "R1" "S1" "Sc" "Rc"

#cannot work, select still holds the lock at Bc
permutation "R1" "S1" "Bc" "Rc" "Sc"
permutation "S1" "R1" "Bc" "Rc" "Sc"

#should work, R does not yet have the read-lock at S1
permutation "R1" "S1" "Sc" "Bc" "Rc"
permutation "S1" "R1" "Sc" "Bc" "Rc"
