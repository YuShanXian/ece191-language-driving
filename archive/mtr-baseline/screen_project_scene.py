import argparse
from mtr_project.screening import screen

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--sample',required=True);p.add_argument('--run',required=True)
    p.add_argument('--preserve-start-ambiguity',action='store_true',help='Use all history-compatible starts; write separate ambiguity_aware_feasibility.json')
    args=p.parse_args();screen(args.sample,args.run,preserve_start_ambiguity=args.preserve_start_ambiguity)
