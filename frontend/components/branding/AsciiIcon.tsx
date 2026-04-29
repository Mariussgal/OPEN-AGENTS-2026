/**
 * Onchor seal — version compacte (équivalent ASCII_ICON_SMALL côté CLI).
 * Downsamplée 1 ligne sur 3 + 1 char sur 3 depuis l'original.
 */
export const ASCII_ICON_SMALL = String.raw`                              
                  .              
                ....             
              .....::            
             .......::           
           ........:::           
          ...........            
         ........-:::::          
        ....:::::-----:::        
       .::::::::::-------::      
      ..    .:::::-----   :      
   .    ......::::-----    .     
   ...     ........::::      :   
   ......     ..::::::      :::  
   ........              :::::   
   ......::....:::::::::::::::   
       ............::::::::      
         ..........::::::        
            ......:::            
                .                
                                 `;

type Props = {
  className?: string;
};

export function AsciiIcon({ className = "" }: Props) {
  return (
    <pre
      aria-hidden
      className={[
        "font-mono leading-[1.05] whitespace-pre text-[--terminal-brand-dim]",
        className,
      ].join(" ")}
    >
      {ASCII_ICON_SMALL}
    </pre>
  );
}
